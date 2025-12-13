from flask import Flask, render_template, request, jsonify
from jinja2 import Template, TemplateSyntaxError, UndefinedError
import json

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

        # Parse variables (support both JSON and key=value format)
        try:
            variables = json.loads(variables_str)
        except json.JSONDecodeError:
            # Try to parse as key=value pairs
            variables = {}
            for line in variables_str.strip().split('\n'):
                if '=' in line:
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
