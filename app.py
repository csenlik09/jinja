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
    return render_template('index.html')

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

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    return jsonify(db.get_vendors())

@app.route('/api/os-types', methods=['GET'])
def get_os_types():
    vendor = request.args.get('vendor')
    return jsonify(db.get_os_types(vendor))

@app.route('/api/templates', methods=['GET'])
def get_templates():
    host_type = request.args.get('host_type')
    vendor = request.args.get('vendor')
    os = request.args.get('os')

    if host_type or vendor or os:
        templates = db.get_templates_by_criteria(host_type, vendor, os)
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
            vendor=data['vendor'],
            os=data['os'],
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

        configs = []

        for row in excel_data:
            host_type = row.get('host_type')
            vendor = row.get('vendor')
            os = row.get('os')

            if not all([host_type, vendor, os]):
                configs.append({
                    'row': row,
                    'success': False,
                    'error': 'Missing required fields: host_type, vendor, or os'
                })
                continue

            # Find matching template
            templates = db.get_templates_by_criteria(host_type, vendor, os)

            if not templates:
                configs.append({
                    'row': row,
                    'success': False,
                    'error': f'No template found for {host_type}/{vendor}/{os}'
                })
                continue

            # Use first matching template
            template_obj = templates[0]
            template_str = template_obj['template_content']

            # Render template with row data
            try:
                template = Template(template_str)
                output = template.render(**row)
                configs.append({
                    'row': row,
                    'success': True,
                    'config': output,
                    'template_name': template_obj['name']
                })
            except Exception as e:
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

        fields = db.get_template_fields(template_id)

        # Extract variables from template
        from jinja2 import meta, Environment
        env = Environment()
        ast = env.parse(template_obj['template_content'])
        variables = meta.find_undeclared_variables(ast)

        # Only use variables, no sample data
        columns = sorted(list(variables))

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

@app.route('/api/vendors', methods=['POST'])
def add_vendor():
    try:
        data = request.get_json()
        db.add_vendor(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/vendors/delete', methods=['POST'])
def remove_vendor():
    try:
        data = request.get_json()
        db.remove_vendor(data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/os-types', methods=['POST'])
def add_os_type():
    try:
        data = request.get_json()
        db.add_os_type(data['vendor'], data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/os-types/delete', methods=['POST'])
def remove_os_type():
    try:
        data = request.get_json()
        db.remove_os_type(data['vendor'], data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
