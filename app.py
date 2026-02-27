from flask import Flask, render_template, request, jsonify, send_file
from jinja2 import Template, TemplateSyntaxError, UndefinedError, Environment, FileSystemLoader, StrictUndefined
import json
import yaml
import pandas as pd
from io import BytesIO
from database import Database
import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from collections import deque, defaultdict
import subprocess
from pathlib import Path
import re

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

# YAML-based configuration model for Config Generator
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / 'config-framework'

render_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / 'templates')),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

def load_yaml(rel_path):
    file_path = CONFIG_DIR / rel_path
    if not file_path.exists():
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

HOSTNAME_MAP = load_yaml('mappings/hostname_map.yaml')
HOST_TYPE_MAP = load_yaml('mappings/host_type_map.yaml')
SWITCH_MAP = load_yaml('mappings/switch_map.yaml')
SWITCH_INVENTORY = load_yaml('mappings/switch_inventory.yaml')
INTERFACE_PROFILES = load_yaml('profiles/interface_profiles.yaml')
INTERFACE_NAMING = load_yaml('platform/interface_naming.yaml')
FEATURE_TRANSLATION = load_yaml('platform/feature_translation.yaml')
CONFIG_TYPES = load_yaml('types/config_types.yaml')

def normalize_input_row(row):
    lookup = {str(k).strip().lower(): v for k, v in row.items()}

    def pick(*keys):
        for key in keys:
            if key in lookup and lookup[key] is not None:
                return str(lookup[key]).strip()
        return ''

    return {
        'hostname': pick('hostname', 'host_name', 'host'),
        'host_port': pick('host_port', 'host port', 'server_port'),
        'switch_name': pick('switch_name', 'switch name', 'switch'),
        'switch_port': pick('switch_port', 'switch port', 'interface'),
        'vlan': pick('vlan'),
        'vip': pick('vip', 'virtual_ip', 'virtual ip')
    }

def resolve_host_type(hostname):
    for rule in HOSTNAME_MAP.get('hostname_rules', []):
        if re.search(rule.get('regex', ''), hostname or ''):
            return rule.get('host_type', 'xcoder')
    return HOSTNAME_MAP.get('default_host_type', 'xcoder')

def resolve_platform(switch_name):
    # 1) Exact switch entries from inventory file
    exact_switches = SWITCH_INVENTORY.get('exact_switches', {})
    for name, facts in exact_switches.items():
        if str(name).strip().lower() == str(switch_name or '').strip().lower():
            return {
                'platform_id': facts.get('platform_id', 'cisco_nxos_n9k'),
                'vendor': facts.get('vendor', ''),
                'os': facts.get('os', ''),
                'model': facts.get('model', '')
            }

    # 2) Regex rules from inventory file
    for rule in SWITCH_INVENTORY.get('regex_rules', []):
        if re.search(rule.get('regex', ''), switch_name or ''):
            facts = rule.get('facts', {})
            return {
                'platform_id': facts.get('platform_id', 'cisco_nxos_n9k'),
                'vendor': facts.get('vendor', ''),
                'os': facts.get('os', ''),
                'model': facts.get('model', '')
            }

    # 3) Backward-compatible fallback to switch_map.yaml
    for rule in SWITCH_MAP.get('switch_rules', []):
        if re.search(rule.get('regex', ''), switch_name or ''):
            return {
                'platform_id': rule.get('platform_id', 'cisco_nxos'),
                'vendor': rule.get('vendor', ''),
                'os': rule.get('os', ''),
                'model': rule.get('model', '')
            }

    # 4) Inventory default, then old default
    default_facts = SWITCH_INVENTORY.get('default_facts')
    if default_facts:
        return {
            'platform_id': default_facts.get('platform_id', 'cisco_nxos_n9k'),
            'vendor': default_facts.get('vendor', ''),
            'os': default_facts.get('os', ''),
            'model': default_facts.get('model', '')
        }

    return SWITCH_MAP.get('default_platform', {'platform_id': 'cisco_nxos_n9k'})

def format_interface_name(platform_id, switch_port):
    naming = INTERFACE_NAMING.get('interface_naming', {}).get(platform_id, {})
    pattern = naming.get('ethernet_pattern', 'Ethernet{switch_port}')

    port_raw = str(switch_port).strip()
    port_raw = re.sub(r'^(?i:ethernet)', '', port_raw)
    port_raw = port_raw.lstrip('/')
    slot = '1'
    port = port_raw

    if '/' in port_raw:
        parts = [p for p in port_raw.split('/') if p != '']
        if len(parts) >= 2:
            slot, port = parts[0], parts[1]
        elif len(parts) == 1:
            port = parts[0]

    try:
        return pattern.format(switch_port=switch_port, slot=slot, port=port)
    except Exception:
        return f"Ethernet{port_raw}"

def build_interface_context(row):
    host_type = resolve_host_type(row['hostname'])
    platform = resolve_platform(row['switch_name'])
    platform_id = platform['platform_id']

    host_to_profile = HOST_TYPE_MAP.get('host_type_to_profile', {})
    default_profile_id = host_to_profile.get('default', 'access_single')
    profile_id = host_to_profile.get(host_type, default_profile_id)
    profile_map = INTERFACE_PROFILES.get('interface_profiles', {})
    profile = profile_map.get(profile_id, profile_map.get(default_profile_id, {}))

    stp_profile = profile.get('stp_profile', 'edge_access')
    storm_profile = profile.get('storm_control_profile', 'none')
    feature_translation = FEATURE_TRANSLATION.get('feature_translation', {})
    stp_commands = feature_translation.get('stp_profile', {})
    storm_commands = feature_translation.get('storm_control_profile', {})
    stp_value = stp_commands.get(stp_profile, {}).get(platform_id, '')
    if isinstance(stp_value, list):
        stp_value = stp_value[0] if stp_value else ''
    storm_value = storm_commands.get(storm_profile, {}).get(platform_id, [])
    if not isinstance(storm_value, list):
        storm_value = [str(storm_value)] if storm_value else []

    return {
        'platform_id': platform_id,
        'host_type': host_type,
        'profile_id': profile_id,
        'interface_name': format_interface_name(platform_id, row['switch_port']),
        'description': f"{row['hostname']}:{row['host_port']}" + (f" VIP:{row['vip']}" if row['vip'] else ''),
        'port_mode': profile.get('port_mode', 'access'),
        'ptp_enabled': bool(profile.get('ptp_enabled', False)),
        'vlan': row['vlan'],
        'stp_command': stp_value,
        'storm_control_commands': storm_value
    }

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

        # Convert to list of dictionaries and normalize expected keys for interface config flow
        raw_data = df.to_dict('records')
        data = [normalize_input_row(row) for row in raw_data]
        columns = ['hostname', 'host_port', 'switch_name', 'switch_port', 'vlan', 'vip']

        app.logger.info(f"Excel file processed successfully: {len(data)} rows loaded")

        return jsonify({'success': True, 'data': data, 'columns': columns})

    except Exception as e:
        app.logger.error(f"Error uploading Excel file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/config-types', methods=['GET'])
def get_config_types():
    return jsonify(CONFIG_TYPES)

@app.route('/api/generate-configs', methods=['POST'])
def generate_configs():
    try:
        data = request.get_json() or {}
        excel_data = data.get('excel_data', [])
        config_type = data.get('config_type', 'interface')

        if not excel_data:
            app.logger.warning("Config generation attempt with no data")
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        if config_type != 'interface':
            return jsonify({'success': False, 'error': f"Configuration type '{config_type}' is not implemented yet"}), 400

        app.logger.info(f"User generating configs from {len(excel_data)} rows")

        template = render_env.get_template('interface/interface_config.j2')
        grouped_data = defaultdict(list)
        configs = []
        success_row_count = 0
        error_row_count = 0
        skipped_count = 0

        for idx, raw in enumerate(excel_data, start=1):
            row = normalize_input_row(raw)
            missing = [k for k in ['hostname', 'host_port', 'switch_name', 'switch_port'] if not row.get(k)]
            if missing:
                skipped_count += 1
                error_row_count += 1
                configs.append({
                    'row': row,
                    'success': False,
                    'error': f"Missing required fields: {', '.join(missing)} (row {idx})"
                })
                continue

            context = build_interface_context(row)
            output = template.render(**context).strip()
            grouped_data[row['switch_name']].append(output)
            success_row_count += 1

        for switch_name, snippets in grouped_data.items():
            configs.append({
                'row': {'switch_name': switch_name, 'row_count': len(snippets)},
                'success': True,
                'config': '\n'.join(snippets).strip(),
                'switch_name': switch_name,
                'row_count': len(snippets)
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
