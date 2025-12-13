"""
Example of loading templates from files
"""

from jinja2 import Environment, FileSystemLoader
import os

# Get the templates directory
template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Create environment with file loader
env = Environment(loader=FileSystemLoader(template_dir))

# Load and render template
template = env.get_template('example.html')
output = template.render(
    title="My Page",
    heading="Welcome to Jinja2",
    items=['Feature 1', 'Feature 2', 'Feature 3']
)

print(output)
