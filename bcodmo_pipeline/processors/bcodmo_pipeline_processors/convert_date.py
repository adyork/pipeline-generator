from datapackage_pipelines.wrapper import ingest, spew
from datapackage_pipelines.utilities.resource_matcher import ResourceMatcher
from datetime import datetime
import logging
import pytz
import re

logging.basicConfig(
    level=logging.WARNING,
)
logger = logging.getLogger(__name__)

parameters, datapackage, resource_iterator = ingest()

resources = ResourceMatcher(parameters.get('resources'))
fields = parameters.get('fields', [])

def modify_datapackage(datapackage_):
    dp_resources = datapackage_.get('resources', [])
    for resource_ in dp_resources:
        if resources.match(resource_['name']):
            new_fields = [{
                'name': f['output_field'],
                'type': 'string',
            } for f in fields]
            resource_['schema']['fields'] += new_fields
    return datapackage_


def process_resource(rows, missing_data_values):
    for row in rows:
        for field in fields:
            input_field = field['input_field']
            if input_field not in row:
                raise Exception(f'Input field {input_field} not found in row')
            row_value = row[input_field]
            if row_value in missing_data_values or row_value is None:
                row[field['name']] = row_value
                continue
            row_value = str(row_value)

            output_field = field['output_field']
            input_format = field['input_format']
            output_format = field['output_format']

            input_timezone = field.get('input_timezone', None)
            output_timezone = field.get('output_timezone', None)
            if not output_timezone:
                output_timezone = 'UTC'
            year = field.get('year', None)

            date_obj = datetime.strptime(row_value, input_format)
            if not date_obj.tzinfo:
                if not input_timezone:
                    raise Exception('Date string does not contain timezone information and timezone was not inputed')
                input_timezone_obj = pytz.timezone(input_timezone)
                date_obj = input_timezone_obj.localize(date_obj)

            if year:
                date_obj = date_obj.replace(year=int(year))

            output_timezone_obj = pytz.timezone(output_timezone)
            output_date_string = date_obj.astimezone(output_timezone_obj).strftime(output_format)
            # Python datetime uses UTC as the timezone string, ISO requires Z
            if output_timezone == 'UTC':
                output_date_string = output_date_string.replace('UTC', 'Z')
            row[output_field] = output_date_string

        yield row


def process_resources(resource_iterator_):
    for resource in resource_iterator_:
        spec = resource.spec
        if not resources.match(spec['name']):
            yield resource
        else:
            missing_data_values = ['']
            for resource_datapackage in datapackage.get('resources', []):
                if resource_datapackage['name'] == spec['name']:
                    missing_data_values = resource_datapackage.get(
                        'schema', {},
                    ).get(
                        'missingValues', ['']
                    )
                    break
            yield process_resource(resource, missing_data_values)


spew(modify_datapackage(datapackage), process_resources(resource_iterator))
