from flask import Flask, render_template, request, jsonify, send_file
from jinja2 import Template, TemplateSyntaxError, UndefinedError
import json
import yaml
import pandas as pd
from io import BytesIO
from database import Database
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialize database
db = Database()

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    response = render_template('index.html')
    from flask import make_response
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/render', methods=['POST'])
def render_jinja():
    try:
        data = request.get_json()
        template_str = data.get('template', '')
        variables_str = data.get('variables', '{}')

        # Parse variables (support JSON, YAML, and key=value format)
        try:
            # First try JSON
            variables = json.loads(variables_str)
        except json.JSONDecodeError:
            try:
                # Then try YAML
                variables = yaml.safe_load(variables_str)
                if variables is None:
                    variables = {}
            except yaml.YAMLError:
                # Finally try key=value pairs
                variables = {}
                for line in variables_str.strip().split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        variables[key.strip()] = value.strip()

        # Create and render template
        template = Template(template_str)
        output = template.render(**variables)

        return jsonify({
            'success': True,
            'output': output
        })

    except TemplateSyntaxError as e:
        return jsonify({
            'success': False,
            'error': f'Template Syntax Error: {str(e)}'
        }), 400

    except UndefinedError as e:
        return jsonify({
            'success': False,
            'error': f'Undefined Variable: {str(e)}'
        }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error: {str(e)}'
        }), 400

# ========== Config Generator API Endpoints ==========

@app.route('/api/host-types', methods=['GET'])
def get_host_types():
    return jsonify(db.get_host_types())

@app.route('/api/port-types', methods=['GET'])
def get_port_types():
    return jsonify(db.get_port_types())

@app.route('/api/switch-os-types', methods=['GET'])
def get_switch_os_types():
    return jsonify(db.get_switch_os_types())

@app.route('/api/templates', methods=['GET'])
def get_templates():
    host_type = request.args.get('host_type')
    port_type = request.args.get('port_type')
    switch_os = request.args.get('switch_os')

    if host_type or port_type or switch_os:
        templates = db.get_templates_by_criteria(host_type, port_type, switch_os)
    else:
        templates = db.get_all_templates()

    return jsonify(templates)

@app.route('/api/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    template = db.get_template(template_id)
    if template:
        fields = db.get_template_fields(template_id)
        template['fields'] = fields
        return jsonify(template)
    return jsonify({'error': 'Template not found'}), 404

@app.route('/api/templates', methods=['POST'])
def create_template():
    try:
        data = request.get_json()
        template_id = db.create_template(
            name=data['name'],
            host_type=data['host_type'],
            port_type=data['port_type'],
            switch_os=data['switch_os'],
            template_content=data['template_content'],
            description=data.get('description', ''),
            fields=data.get('fields', [])
        )
        return jsonify({'success': True, 'template_id': template_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    try:
        data = request.get_json()
        db.update_template(template_id, **data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        db.delete_template(template_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload-excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload Excel file.'}), 400

        # Read Excel file
        df = pd.read_excel(file, engine='openpyxl')

        # Replace NaN values with empty strings to avoid template errors
        df = df.fillna('')

        # Convert to list of dictionaries
        data = df.to_dict('records')

        return jsonify({'success': True, 'data': data, 'columns': list(df.columns)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/generate-configs', methods=['POST'])
def generate_configs():
    try:
        data = request.get_json()
        excel_data = data.get('excel_data', [])

        if not excel_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Group rows by template name
        from collections import defaultdict
        grouped_data = defaultdict(list)

        for row in excel_data:
            # Debug: Print first row to see actual column names
            if excel_data.index(row) == 0:
                print(f"DEBUG: First row keys: {list(row.keys())}")
                print(f"DEBUG: First row values: {row}")

            template_name = row.get('template')
            switch_name = row.get('switch_name')
            switch_port = row.get('switch_port')

            # Skip rows missing required fields
            if not template_name or not switch_name or switch_port is None or str(switch_port).strip() == '':
                print(f"DEBUG: Skipping row - template={template_name}, switch_name={switch_name}, switch_port={switch_port}")
                continue

            # Normalize template name for grouping
            key = str(template_name).strip()
            grouped_data[key].append(row)

        # Debug logging
        print(f"DEBUG: Total rows: {len(excel_data)}")
        print(f"DEBUG: Number of template groups: {len(grouped_data)}")
        for key, rows in grouped_data.items():
            print(f"DEBUG: Template '{key}': {len(rows)} rows")

        configs = []

        # Process each template group
        for template_name, rows in grouped_data.items():
            # Find template by name
            template_obj = db.get_template_by_name(template_name)

            if not template_obj:
                # No template found - mark all rows in this group as errors
                for row in rows:
                    configs.append({
                        'row': row,
                        'success': False,
                        'error': f'No template found with name: {template_name}'
                    })
                continue

            template_str = template_obj['template_content']

            # Render template with grouped data
            try:
                template = Template(template_str)
                # Pass all rows as 'ports' and 'switches' list + individual fields from first row
                render_context = rows[0].copy() if rows else {}
                render_context['ports'] = rows
                render_context['switches'] = rows  # Keep for backward compatibility

                # Debug: Print sample row to see actual values
                if rows:
                    print(f"DEBUG: Sample row for template '{template_name}': {rows[0]}")
                    if 'ptp_vlan' in rows[0]:
                        print(f"DEBUG: ptp_vlan value: '{rows[0]['ptp_vlan']}' (type: {type(rows[0]['ptp_vlan']).__name__})")

                output = template.render(**render_context)

                # Return one config for the entire group
                configs.append({
                    'row': {'template': template_name, 'row_count': len(rows)},
                    'success': True,
                    'config': output,
                    'template_name': template_obj['name']
                })
            except Exception as e:
                # Template rendering failed - mark all rows in this group as errors
                for row in rows:
                    configs.append({
                        'row': row,
                        'success': False,
                        'error': f'Template rendering error: {str(e)}'
                    })

        return jsonify({'success': True, 'configs': configs})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/download-template-excel/<int:template_id>', methods=['GET'])
def download_template_excel(template_id):
    try:
        template_obj = db.get_template(template_id)

        if not template_obj:
            return jsonify({'error': 'Template not found'}), 404

        # Extract variables from template
        import re
        template_content = template_obj['template_content']

        # Find all variable references like p.variable_name, row.variable_name, etc.
        # Look for patterns: p.field, row.field, item.field, sw.field
        field_pattern = r'(?:p|row|item|switch|port|sw)\.([\w_]+)'
        matches = re.findall(field_pattern, template_content)

        # Also find field names in groupby('field_name') patterns
        groupby_pattern = r"groupby\(['\"](\w+)['\"]\)"
        groupby_fields = re.findall(groupby_pattern, template_content)

        # Combine all field names
        all_fields = list(set(matches + groupby_fields))

        # Filter out Jinja2/Python built-in methods and properties
        excluded = ['list', 'dict', 'items', 'keys', 'values', 'append', 'join', 'split',
                    'strip', 'upper', 'lower', 'replace', 'format', 'grouper', 'first',
                    'last', 'index', 'count', 'length', 'defined', 'groupby']
        field_names = sorted([f for f in all_fields if f not in excluded])

        # Create column list with host_type, port_type, switch_os as first 3 columns
        columns = ['host_type', 'port_type', 'switch_os'] + field_names

        df = pd.DataFrame(columns=columns)

        # Save to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Config Data')
        output.seek(0)

        filename = f'template_{template_obj["name"]}.xlsx'

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ========== Metadata Management API Endpoints ==========

@app.route('/api/host-types', methods=['POST'])
def add_host_type():
    try:
        data = request.get_json()
        db.add_host_type(data['name'], data.get('description', ''))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/host-types/delete', methods=['POST'])
def remove_host_type():
    try:
        data = request.get_json()
        db.remove_host_type(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/port-types', methods=['POST'])
def add_port_type():
    try:
        data = request.get_json()
        db.add_port_type(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/port-types/delete', methods=['POST'])
def remove_port_type():
    try:
        data = request.get_json()
        db.remove_port_type(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/switch-os-types', methods=['POST'])
def add_switch_os_type():
    try:
        data = request.get_json()
        db.add_switch_os_type(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/switch-os-types/delete', methods=['POST'])
def remove_switch_os_type():
    try:
        data = request.get_json()
        db.remove_switch_os_type(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
