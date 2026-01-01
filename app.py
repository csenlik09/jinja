from flask import Flask, render_template, request, jsonify, send_file
from jinja2 import Template, TemplateSyntaxError, UndefinedError
import json
import yaml
import pandas as pd
from io import BytesIO
from database import Database
import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from collections import deque
import subprocess

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Get current version from git
def get_version():
    try:
        version = subprocess.check_output(['git', 'describe', '--tags', '--always'], cwd=os.path.dirname(__file__)).decode('utf-8').strip()
        return version
    except:
        return 'v1.5'  # Fallback version

APP_VERSION = get_version()

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

# File handler
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
console_handler.setLevel(logging.INFO)

# Configure app logger
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.INFO)

# In-memory log buffer for quick access (keep last 500 logs)
log_buffer = deque(maxlen=500)

class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno
        }
        log_buffer.append(log_entry)

buffer_handler = BufferHandler()
buffer_handler.setLevel(logging.DEBUG)
app.logger.addHandler(buffer_handler)

app.logger.info('Application starting...')

# Initialize database
db = Database()

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    response = render_template('index.html', version=APP_VERSION)
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
        app.logger.error(f'Template syntax error in Jinja Tester: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Template Syntax Error: {str(e)}'
        }), 400

    except UndefinedError as e:
        app.logger.error(f'Undefined variable in Jinja Tester: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Undefined Variable: {str(e)}'
        }), 400

    except Exception as e:
        app.logger.error(f'Error in Jinja Tester: {str(e)}')
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
        app.logger.info(f"User creating template: {data['name']} ({data['host_type']}/{data['port_type']}/{data['switch_os']})")
        template_id = db.create_template(
            name=data['name'],
            host_type=data['host_type'],
            port_type=data['port_type'],
            switch_os=data['switch_os'],
            template_content=data['template_content'],
            version_description=data.get('version_description', '')
        )
        app.logger.info(f"Template created successfully with ID: {template_id}")
        return jsonify({'success': True, 'template_id': template_id})
    except Exception as e:
        app.logger.error(f"Error creating template: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    try:
        data = request.get_json()
        app.logger.info(f"User updating template ID {template_id}: {data}")
        db.update_template(template_id, **data)
        app.logger.info(f"Template {template_id} updated successfully")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error updating template {template_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        template = db.get_template(template_id)
        app.logger.warning(f"User deleting template ID {template_id}: {template['name'] if template else 'Unknown'}")
        db.delete_template(template_id)
        app.logger.info(f"Template {template_id} deleted successfully")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting template {template_id}: {str(e)}")
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
        app.logger.info(f"User creating new version for template ID {template_id}: {data.get('version_name')}")
        version_num = db.create_template_version(
            template_id,
            data.get('template_content'),
            data.get('version_name'),
            data.get('version_description', '')
        )
        app.logger.info(f"Version {version_num} created for template {template_id}")
        return jsonify({'success': True, 'version': version_num})
    except Exception as e:
        app.logger.error(f"Error creating version for template {template_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['GET'])
def get_template_version(template_id, version):
    try:
        version_data = db.get_template_version(template_id, version)
        if version_data:
            return jsonify(version_data)
        return jsonify({'error': 'Version not found'}), 404
    except Exception as e:
        app.logger.error(f"Error getting version {version} for template {template_id}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['PUT'])
def update_template_version(template_id, version):
    try:
        data = request.get_json()
        app.logger.info(f"User updating version {version} for template {template_id}")
        db.update_template_version(template_id, version, **data)
        app.logger.info(f"Version {version} updated for template {template_id}")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error updating version {version} for template {template_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/versions/<int:version>', methods=['DELETE'])
def delete_template_version(template_id, version):
    try:
        app.logger.warning(f"User deleting version {version} for template {template_id}")
        db.delete_template_version(template_id, version)
        app.logger.info(f"Version {version} deleted for template {template_id}")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting version {version} for template {template_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/active-version/<int:version>', methods=['POST'])
def set_active_version(template_id, version):
    try:
        app.logger.info(f"User setting active version to {version} for template {template_id}")
        db.set_active_version(template_id, version)
        app.logger.info(f"Active version set to {version} for template {template_id}")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error setting active version for template {template_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload-excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files:
            app.logger.warning("Excel upload attempt with no file")
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            app.logger.warning("Excel upload attempt with empty filename")
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith(('.xlsx', '.xls')):
            app.logger.warning(f"Invalid file type uploaded: {file.filename}")
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload Excel file.'}), 400

        app.logger.info(f"User uploaded Excel file: {file.filename}")

        # Read Excel file
        df = pd.read_excel(file, engine='openpyxl')

        # Replace NaN values with empty strings to avoid template errors
        df = df.fillna('')

        # Convert to list of dictionaries
        data = df.to_dict('records')

        app.logger.info(f"Excel file processed successfully: {len(data)} rows loaded")

        return jsonify({'success': True, 'data': data, 'columns': list(df.columns)})

    except Exception as e:
        app.logger.error(f"Error uploading Excel file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/generate-configs', methods=['POST'])
def generate_configs():
    try:
        data = request.get_json()
        excel_data = data.get('excel_data', [])

        if not excel_data:
            app.logger.warning("Config generation attempt with no data")
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        app.logger.info(f"User generating configs from {len(excel_data)} rows")

        # Group rows by template name
        from collections import defaultdict
        grouped_data = defaultdict(list)
        skipped_count = 0

        for row in excel_data:
            template_name = row.get('template')
            switch_name = row.get('switch_name')
            switch_port = row.get('switch_port')

            # Skip rows missing required fields
            if not template_name or not switch_name or switch_port is None or str(switch_port).strip() == '':
                app.logger.debug(f"Skipping row - template={template_name}, switch_name={switch_name}, switch_port={switch_port}")
                skipped_count += 1
                continue

            # Normalize template name for grouping
            key = str(template_name).strip()
            grouped_data[key].append(row)

        app.logger.info(f"Grouped data: {len(grouped_data)} template(s), {skipped_count} rows skipped")

        configs = []
        success_row_count = 0
        error_row_count = 0

        # Process each template group
        for template_name, rows in grouped_data.items():
            # Find template by name
            template_obj = db.get_template_by_name(template_name)

            if not template_obj:
                # No template found - mark all rows in this group as errors
                app.logger.warning(f"Template not found: {template_name} (affected {len(rows)} rows)")
                error_row_count += len(rows)
                for row in rows:
                    configs.append({
                        'row': row,
                        'success': False,
                        'error': f'No template found with name: {template_name}'
                    })
                continue

            app.logger.info(f"Rendering template '{template_name}' for {len(rows)} rows")
            template_str = template_obj['template_content']

            # Render template with grouped data
            try:
                template = Template(template_str)
                # Pass all rows as 'ports' and 'switches' list + individual fields from first row
                render_context = rows[0].copy() if rows else {}
                render_context['ports'] = rows
                render_context['switches'] = rows  # Keep for backward compatibility

                output = template.render(**render_context)

                # Return one config for the entire group
                success_row_count += len(rows)
                app.logger.info(f"Successfully rendered config for template '{template_name}' ({len(rows)} rows)")
                configs.append({
                    'row': {'template': template_name, 'row_count': len(rows)},
                    'success': True,
                    'config': output,
                    'template_name': template_obj['name'],
                    'row_count': len(rows)
                })
            except Exception as e:
                # Template rendering failed - mark all rows in this group as errors
                app.logger.error(f"Template rendering error for '{template_name}': {str(e)}")
                error_row_count += len(rows)
                for row in rows:
                    configs.append({
                        'row': row,
                        'success': False,
                        'error': f'Template rendering error: {str(e)}'
                    })

        app.logger.info(f"Config generation complete: {success_row_count} success, {error_row_count} errors, {skipped_count} skipped")

        return jsonify({
            'success': True,
            'configs': configs,
            'success_row_count': success_row_count,
            'error_row_count': error_row_count,
            'skipped_row_count': skipped_count
        })

    except Exception as e:
        app.logger.error(f"Error in config generation: {str(e)}")
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
        app.logger.info("User exporting database")
        db_path = 'data/templates.db'
        app.logger.info(f"Database exported successfully: {db_path}")
        return send_file(
            db_path,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name=f'templates_backup_{datetime.now().strftime("%Y-%m-%d")}.db'
        )
    except Exception as e:
        app.logger.error(f"Error exporting database: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/import-database', methods=['POST'])
def import_database():
    try:
        if 'file' not in request.files:
            app.logger.warning("Database import attempt with no file")
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            app.logger.warning("Database import attempt with empty filename")
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith('.db'):
            app.logger.warning(f"Invalid database file uploaded: {file.filename}")
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload .db file.'}), 400

        app.logger.warning(f"User restoring database from file: {file.filename}")

        # Save the uploaded file to replace the current database
        db_path = 'data/templates.db'

        # Create backup of current database before replacing
        backup_path = f'data/templates_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            app.logger.info(f"Current database backed up to: {backup_path}")

        # Save the new database file
        file.save(db_path)

        # Reinitialize the database connection
        global db
        db = Database()

        app.logger.info("Database restored successfully")
        return jsonify({'success': True})

    except Exception as e:
        app.logger.error(f"Error restoring database: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== Logging API Endpoints ==========

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        level_filter = request.args.get('level', 'all')
        limit = int(request.args.get('limit', 1000))  # Default to last 1000 logs

        # Read logs from file
        logs = []
        log_file = 'logs/app.log'

        if os.path.exists(log_file):
            import re
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Parse log lines
            # Format: 2026-01-01 20:51:09,668 INFO: User uploaded Excel file: template_JINJA-XC-DATA.xlsx [in /app/app.py:295]
            log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (\w+): (.+) \[in (.+?):(\d+)\]')

            for line in lines:
                match = log_pattern.match(line)
                if match:
                    timestamp, level, message, filepath, line_no = match.groups()
                    module = os.path.basename(filepath).replace('.py', '')

                    # Filter by level if specified
                    if level_filter == 'all' or level == level_filter:
                        logs.append({
                            'timestamp': timestamp.replace(',', '.'),
                            'level': level,
                            'message': message,
                            'module': module,
                            'line': int(line_no)
                        })

        # Return the most recent logs (up to limit)
        logs = logs[-limit:] if len(logs) > limit else logs

        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        app.logger.error(f'Error retrieving logs: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    try:
        # Clear the log file
        log_file = 'logs/app.log'
        if os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('')

        log_buffer.clear()
        app.logger.info('Logs cleared by user')
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f'Error clearing logs: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 400

# Add logging to important operations (reduced verbosity)
@app.before_request
def log_request():
    # Skip logging for static files and log endpoint itself to avoid clutter
    if request.endpoint and not request.endpoint.startswith('static') and not request.path.startswith('/api/logs'):
        app.logger.debug(f'{request.method} {request.path}')

@app.after_request
def log_response(response):
    # Only log errors or skip log endpoint
    if request.endpoint and not request.endpoint.startswith('static') and not request.path.startswith('/api/logs'):
        if response.status_code >= 400:
            app.logger.error(f'{request.method} {request.path} - {response.status_code}')
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
