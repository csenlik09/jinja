#!/usr/bin/env python3
import requests
import json

template = """{# --- Leaf Selection --- #}
{% if details.side == 'A' %}
{{ name_leaf_a }}
{% else %}
{{ name_leaf_b }}
{% endif %}

{# --- Ethernet Ports Configuration --- #}
{% for port in range(interfaces.ethernet_start, interfaces.ethernet_end + 1) %}
interface Ethernet1/{{ port }}
  {% if details.side == 'A' %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}-P-{{ host_port_a }}-DATA
  {% else %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}-P-{{ host_port_b }}-DATA
  {% endif %}
  switchport
  switchport mode trunk
  switchport trunk native vlan {{ interfaces.trunk_vlan }}
{% if interfaces.ptp_vlan is defined and interfaces.ptp_vlan %}
  ptp
  ptp vlan {{ interfaces.ptp_vlan }}
{% endif %}
  channel-group {{ interfaces.port_channel_start + loop.index0 }} mode active
  spanning-tree port type edge trunk
  no shutdown
  !
{% endfor %}
!

{# --- Port-channel Configuration --- #}
{% for port_channel in range(interfaces.port_channel_start, interfaces.port_channel_end + 1) %}
interface port-channel{{ port_channel }}
  {% if details.side == 'A' %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}-BOND
  {% else %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}-BOND
  {% endif %}
  switchport
  switchport mode trunk
  switchport trunk native vlan {{ interfaces.trunk_vlan }}
  vpc {{ port_channel }}
  no lacp suspend-individual
  spanning-tree port type edge trunk
  !
{% endfor %}
!

{# --- Out-of-Band Device Name --- #}
{{ name_oob }}

{# --- OOB Ports Configuration --- #}
{% for port in range(interfaces.oob_ethernet_start, interfaces.oob_ethernet_end + 1) %}
interface GigabitEthernet1/0/{{ port }}
  {% if details.side == 'A' %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}.P-OOB
  {% else %}
  description {{ host_type }}{{ '%02d' % (interfaces.description_start | int + loop.index0) }}-{{ host_type_2 }}{{ interfaces.xc_type_number }}.P-OOB
  {% endif %}
  switchport access vlan {{ interfaces.oob_vlan }}
  switchport mode access
  no shutdown
  !
{% endfor %}
"""

variables = {
  "name_leaf_a": "LEAF041501.EWR1",
  "name_leaf_b": "LEAF041502.EWR1",
  "name_oob": "OSW0415.EWR1",
  "host_type": "SEG",
  "host_type_2": "LIN01",
  "host_port_a": "AIOM_01",
  "host_port_b": "P1/1",
  "details": {
    "role": "Leaf",
    "location": "EWR1",
    "software": "NXOS",
    "side": "A"
  },
  "interfaces": {
    "description_start": 1,
    "ethernet_start": 21,
    "ethernet_end": 24,
    "port_channel_start": 321,
    "port_channel_end": 324,
    "oob_ethernet_start": 14,
    "oob_ethernet_end": 17,
    "trunk_vlan": 1202,
    "oob_vlan": 302,
    "ptp_vlan": 3001,
    "xc_type_number": ""
  }
}

try:
    response = requests.post('http://localhost/render',
                            json={'template': template, 'variables': json.dumps(variables)})
    result = response.json()
    if result.get('success'):
        print('✅ SUCCESS! Template rendered correctly.')
        print('\n' + '='*60)
        print(result['output'])
        print('='*60)
    else:
        print('❌ ERROR:', result.get('error'))
except Exception as e:
    print('❌ Exception:', e)
