# Jinja Template Project

A Python project for working with Jinja2 templating engine.

## Features

- Template rendering examples
- Custom filters and functions
- Sample templates for common use cases

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from jinja2 import Environment, FileSystemLoader

# Load templates
env = Environment(loader=FileSystemLoader('templates'))
template = env.get_template('example.html')

# Render with context
output = template.render(title="Hello", content="World")
print(output)
```

## Project Structure

```
.
├── templates/          # Jinja2 template files
├── examples/          # Example scripts
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

## License

MIT
