from flask import Flask, render_template, request, jsonify, send_file
from jinja2 import Template, TemplateSyntaxError, UndefinedError
import json
import yaml
import pandas as pd
from io import BytesIO
from database import Database
import os
from datetime import datetime

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
            version_description=data.get('version_description', '')
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

@app.route('/api/templates/<int:template_id>/versions', methods=['GET'])
def get_template_versions(template_id):
    try:
        versions = db.get_template_versions(template_id)
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions', methods=['POST'])
def create_template_version(template_id):
    try:
        data = request.get_json()
        version_num = db.create_template_version(
            template_id,
            data.get('template_content'),
            data.get('version_name'),
            data.get('version_description', '')
        )
        return jsonify({'success': True, 'version': version_num})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['GET'])
def get_template_version(template_id, version):
    try:
        version_data = db.get_template_version(template_id, version)
        if version_data:
            return jsonify(version_data)
        return jsonify({'error': 'Version not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['PUT'])
def update_template_version(template_id, version):
    try:
        data = request.get_json()
        db.update_template_version(template_id, version, **data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['DELETE'])
def delete_template_version(template_id, version):
    try:
        db.delete_template_version(template_id, version)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/active-version/<int:version>', methods=['POST'])
def set_active_version(template_id, version):
    try:
        db.set_active_version(template_id, version)
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
        skipped_count = 0

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
                skipped_count += 1
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
        success_row_count = 0
        error_row_count = 0

        # Process each template group
        for template_name, rows in grouped_data.items():
            # Find template by name
            template_obj = db.get_template_by_name(template_name)

            if not template_obj:
                # No template found - mark all rows in this group as errors
                error_row_count += len(rows)
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
                success_row_count += len(rows)
                configs.append({
                    'row': {'template': template_name, 'row_count': len(rows)},
                    'success': True,
                    'config': output,
                    'template_name': template_obj['name'],
                    'row_count': len(rows)
                })
            except Exception as e:
                # Template rendering failed - mark all rows in this group as errors
                error_row_count += len(rows)
                for row in rows:
                    configs.append({
                        'row': row,
                        'success': False,
                        'error': f'Template rendering error: {str(e)}'
                    })

        return jsonify({
            'success': True,
            'configs': configs,
            'success_row_count': success_row_count,
            'error_row_count': error_row_count,
            'skipped_row_count': skipped_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

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

@app.route('/api/export-database', methods=['GET'])
def export_database():
    try:
        db_path = 'data/templates.db'
        return send_file(
            db_path,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name=f'templates_backup_{datetime.now().strftime("%Y-%m-%d")}.db'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/import-database', methods=['POST'])
def import_database():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload .db file.'}), 400

        # Save the uploaded file to replace the current database
        db_path = 'data/templates.db'

        # Create backup of current database before replacing
        backup_path = f'data/templates_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)

        # Save the new database file
        file.save(db_path)

        # Reinitialize the database connection
        global db
        db = Database()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
