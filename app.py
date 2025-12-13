from flask import Flask, render_template, request, jsonify
from jinja2 import Template, TemplateSyntaxError, UndefinedError
import json
import yaml

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
