"""
Basic Jinja2 template rendering example
"""

from jinja2 import Template

# Simple string template
template = Template("Hello {{ name }}!")
output = template.render(name="World")
print(output)

# Template with loop
template = Template("""
<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% endfor %}
</ul>
""")

output = template.render(items=['Apple', 'Banana', 'Orange'])
print(output)

# Template with conditional
template = Template("""
{% if user %}
    Hello {{ user }}!
{% else %}
    Hello Guest!
{% endif %}
""")

print(template.render(user="Alice"))
print(template.render())
