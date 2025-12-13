import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path='templates.db'):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host_type TEXT NOT NULL,
                vendor TEXT NOT NULL,
                os TEXT NOT NULL,
                template_content TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(host_type, vendor, os, name)
            )
        ''')

        # Host types table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS host_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            )
        ''')

        # Vendors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')

        # OS types table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS os_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(vendor, name)
            )
        ''')

        # Template fields table (for dynamic Excel column generation)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS template_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                required BOOLEAN DEFAULT 1,
                default_value TEXT,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
            )
        ''')

        # Insert default host types
        default_host_types = [
            ('Leaf', 'Leaf switch'),
            ('Spine', 'Spine switch'),
            ('Border', 'Border/Edge switch'),
            ('Access', 'Access switch'),
            ('Core', 'Core switch')
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO host_types (name, description) VALUES (?, ?)',
            default_host_types
        )

        # Insert default vendors
        default_vendors = [
            ('Cisco',),
            ('Arista',),
            ('Juniper',),
            ('Dell',),
            ('HP',)
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO vendors (name) VALUES (?)',
            default_vendors
        )

        # Insert default OS types
        default_os = [
            ('Cisco', 'NXOS'),
            ('Cisco', 'IOS'),
            ('Cisco', 'IOS-XE'),
            ('Cisco', 'IOS-XR'),
            ('Arista', 'EOS'),
            ('Juniper', 'Junos'),
            ('Dell', 'DNOS'),
            ('HP', 'Comware')
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO os_types (vendor, name) VALUES (?, ?)',
            default_os
        )

        conn.commit()
        conn.close()

    # Template CRUD operations
    def create_template(self, name, host_type, vendor, os, template_content, description='', fields=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO templates (name, host_type, vendor, os, template_content, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, host_type, vendor, os, template_content, description))

        template_id = cursor.lastrowid

        # Add template fields if provided
        if fields:
            for field in fields:
                cursor.execute('''
                    INSERT INTO template_fields (template_id, field_name, field_type, required, default_value)
                    VALUES (?, ?, ?, ?, ?)
                ''', (template_id, field['name'], field['type'], field.get('required', True), field.get('default', '')))

        conn.commit()
        conn.close()
        return template_id

    def get_template(self, template_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM templates WHERE id = ?', (template_id,))
        template = cursor.fetchone()
        conn.close()
        return dict(template) if template else None

    def get_templates_by_criteria(self, host_type=None, vendor=None, os=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM templates WHERE 1=1'
        params = []

        if host_type:
            query += ' AND host_type = ?'
            params.append(host_type)
        if vendor:
            query += ' AND vendor = ?'
            params.append(vendor)
        if os:
            query += ' AND os = ?'
            params.append(os)

        cursor.execute(query, params)
        templates = cursor.fetchall()
        conn.close()
        return [dict(t) for t in templates]

    def get_all_templates(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM templates ORDER BY host_type, vendor, os, name')
        templates = cursor.fetchall()
        conn.close()
        return [dict(t) for t in templates]

    def update_template(self, template_id, **kwargs):
        conn = self.get_connection()
        cursor = conn.cursor()

        allowed_fields = ['name', 'host_type', 'vendor', 'os', 'template_content', 'description']
        updates = []
        values = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f'{key} = ?')
                values.append(value)

        if updates:
            values.append(datetime.now())
            values.append(template_id)
            query = f"UPDATE templates SET {', '.join(updates)}, updated_at = ? WHERE id = ?"
            cursor.execute(query, values)

        conn.commit()
        conn.close()

    def delete_template(self, template_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM templates WHERE id = ?', (template_id,))
        conn.commit()
        conn.close()

    # Get metadata
    def get_host_types(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM host_types ORDER BY name')
        results = cursor.fetchall()
        conn.close()
        return [r['name'] for r in results]

    def get_vendors(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM vendors ORDER BY name')
        results = cursor.fetchall()
        conn.close()
        return [r['name'] for r in results]

    def get_os_types(self, vendor=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if vendor:
            cursor.execute('SELECT name FROM os_types WHERE vendor = ? ORDER BY name', (vendor,))
        else:
            cursor.execute('SELECT vendor, name FROM os_types ORDER BY vendor, name')
        results = cursor.fetchall()
        conn.close()
        if vendor:
            return [r['name'] for r in results]
        return [{'vendor': r['vendor'], 'name': r['name']} for r in results]

    def get_template_fields(self, template_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM template_fields WHERE template_id = ?', (template_id,))
        fields = cursor.fetchall()
        conn.close()
        return [dict(f) for f in fields]
