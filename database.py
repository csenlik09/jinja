import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path='data/templates.db'):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if templates table exists and needs migration
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        table_exists = cursor.fetchone()

        if table_exists:
            # Check if we need to migrate from old schema
            cursor.execute("PRAGMA table_info(templates)")
            columns = cursor.fetchall()

            # Check constraints - if old schema, migrate
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='templates'")
            table_sql = cursor.fetchone()
            if table_sql and 'UNIQUE(host_type, vendor, os, name)' in table_sql[0]:
                # Migrate from old schema
                print("Migrating templates table to new schema...")
                cursor.execute('''
                    CREATE TABLE templates_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        host_type TEXT NOT NULL,
                        vendor TEXT NOT NULL,
                        os TEXT NOT NULL,
                        template_content TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(host_type, vendor, os)
                    )
                ''')

                # Copy data - keep only the first template for each combination
                cursor.execute('''
                    INSERT INTO templates_new (id, name, host_type, vendor, os, template_content, description, created_at, updated_at)
                    SELECT MIN(id), name, host_type, vendor, os, template_content, description, created_at, updated_at
                    FROM templates
                    GROUP BY host_type, vendor, os
                ''')

                cursor.execute('DROP TABLE templates')
                cursor.execute('ALTER TABLE templates_new RENAME TO templates')
                print("Migration complete!")

        # Check if we need to migrate from vendor/os to port_type/switch_os
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        table_exists = cursor.fetchone()

        if table_exists:
            cursor.execute("PRAGMA table_info(templates)")
            columns = {col[1]: col for col in cursor.fetchall()}

            if 'vendor' in columns or 'os' in columns:
                print("Migrating templates table from vendor/os to port_type/switch_os...")
                cursor.execute('''
                    CREATE TABLE templates_migrated (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        host_type TEXT NOT NULL,
                        port_type TEXT NOT NULL,
                        switch_os TEXT NOT NULL,
                        template_content TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(host_type, port_type, switch_os)
                    )
                ''')

                cursor.execute('''
                    INSERT INTO templates_migrated (id, name, host_type, port_type, switch_os, template_content, description, created_at, updated_at)
                    SELECT id, name, host_type, vendor, os, template_content, description, created_at, updated_at
                    FROM templates
                ''')

                cursor.execute('DROP TABLE templates')
                cursor.execute('ALTER TABLE templates_migrated RENAME TO templates')
                print("Templates table migration complete!")

        # Templates table - ONE template per host_type/port_type/switch_os combination
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host_type TEXT NOT NULL,
                port_type TEXT NOT NULL,
                switch_os TEXT NOT NULL,
                active_version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(host_type, port_type, switch_os)
            )
        ''')

        # Check if old template_versions table exists with wrong schema and drop it first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='template_versions'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(template_versions)")
            version_columns = {col[1]: col for col in cursor.fetchall()}

            # If old schema (missing version_name), drop it
            if 'version_name' not in version_columns:
                print("Dropping old template_versions table with incompatible schema...")
                cursor.execute('DROP TABLE template_versions')

        # Migration: Rename version column to active_version and move content to versions table
        cursor.execute("PRAGMA table_info(templates)")
        columns = {col[1]: col for col in cursor.fetchall()}

        if 'template_content' in columns:
            print("Migrating templates to new version system...")

            # Create new templates table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS templates_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    host_type TEXT NOT NULL,
                    port_type TEXT NOT NULL,
                    switch_os TEXT NOT NULL,
                    active_version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(host_type, port_type, switch_os)
                )
            ''')

            # Copy template metadata
            cursor.execute('''
                INSERT INTO templates_new (id, name, host_type, port_type, switch_os, active_version, created_at, updated_at)
                SELECT id, name, host_type, port_type, switch_os,
                       COALESCE(version, 1) as active_version,
                       created_at, updated_at
                FROM templates
            ''')

            # Get template content to migrate
            cursor.execute('SELECT id, template_content, description, COALESCE(version, 1) as version FROM templates')
            old_templates = cursor.fetchall()

            # Drop old templates table and rename new one
            cursor.execute('DROP TABLE templates')
            cursor.execute('ALTER TABLE templates_new RENAME TO templates')
            print("Templates table migration complete!")

            # Now create template_versions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS template_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    version_name TEXT NOT NULL,
                    version_description TEXT,
                    template_content TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(template_id, version),
                    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
                )
            ''')

            # Migrate content to template_versions
            for tmpl in old_templates:
                cursor.execute('''
                    INSERT INTO template_versions
                    (template_id, version, version_name, version_description, template_content, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (tmpl[0], tmpl[3], f'v{tmpl[3]}', tmpl[2], tmpl[1]))

            print("Template versions migration complete!")
        else:
            # Create template_versions table if not migrating
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS template_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    version_name TEXT NOT NULL,
                    version_description TEXT,
                    template_content TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(template_id, version),
                    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
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

        # Migrate vendors table to port_types
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vendors'")
        if cursor.fetchone():
            print("Migrating vendors table to port_types...")
            cursor.execute('ALTER TABLE vendors RENAME TO port_types')
            print("Vendors table renamed to port_types!")

        # Port types table (formerly vendors)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS port_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')

        # Migrate os_types to switch_os_types
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='os_types'")
        if cursor.fetchone():
            print("Migrating os_types table to switch_os_types...")
            cursor.execute('ALTER TABLE os_types RENAME TO switch_os_types')
            print("OS types table renamed to switch_os_types!")

        # Switch OS types table (formerly os_types)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS switch_os_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
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

        # No default values - user will create their own host types, vendors (port types), and OS types

        conn.commit()
        conn.close()

    # Template CRUD operations
    def create_template(self, name, host_type, port_type, switch_os, template_content, version_description='', fields=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create template metadata
            cursor.execute('''
                INSERT INTO templates (name, host_type, port_type, switch_os, active_version)
                VALUES (?, ?, ?, ?, 1)
            ''', (name, host_type, port_type, switch_os))

            template_id = cursor.lastrowid

            # Create first version
            cursor.execute('''
                INSERT INTO template_versions (template_id, version, version_name, version_description, template_content, is_active)
                VALUES (?, 1, 'v1', ?, ?, 1)
            ''', (template_id, version_description, template_content))

            conn.commit()
            return template_id
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f'A template already exists for {host_type}/{port_type}/{switch_os}. Only one template is allowed per combination.')
        finally:
            conn.close()

    def get_template(self, template_id):
        """Get template with its active version content"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.*, tv.template_content, tv.version_description
            FROM templates t
            LEFT JOIN template_versions tv ON t.id = tv.template_id AND tv.version = t.active_version
            WHERE t.id = ?
        ''', (template_id,))

        template = cursor.fetchone()
        conn.close()
        return dict(template) if template else None

    def get_template_by_name(self, name):
        """Get template by name (case-insensitive) with active version content"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.*, tv.template_content, tv.version_description
            FROM templates t
            LEFT JOIN template_versions tv ON t.id = tv.template_id AND tv.version = t.active_version
            WHERE LOWER(t.name) = LOWER(?)
        ''', (name,))

        template = cursor.fetchone()
        conn.close()
        return dict(template) if template else None

    def get_templates_by_criteria(self, host_type=None, port_type=None, switch_os=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM templates WHERE 1=1'
        params = []

        if host_type:
            query += ' AND host_type = ?'
            params.append(host_type)
        if port_type:
            query += ' AND port_type = ?'
            params.append(port_type)
        if switch_os:
            query += ' AND switch_os = ?'
            params.append(switch_os)

        cursor.execute(query, params)
        templates = cursor.fetchall()
        conn.close()
        return [dict(t) for t in templates]

    def get_all_templates(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM templates ORDER BY host_type, port_type, switch_os, name')
        templates = cursor.fetchall()
        conn.close()
        return [dict(t) for t in templates]

    def update_template(self, template_id, **kwargs):
        """Update template metadata only (name, host_type, port_type, switch_os)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            allowed_fields = ['name', 'host_type', 'port_type', 'switch_os']
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
        except sqlite3.IntegrityError as e:
            conn.rollback()
            host_type = kwargs.get('host_type', 'unknown')
            port_type = kwargs.get('port_type', 'unknown')
            switch_os = kwargs.get('switch_os', 'unknown')
            raise ValueError(f'A template already exists for {host_type}/{port_type}/{switch_os}. Only one template is allowed per combination.')
        finally:
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

    def get_port_types(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM port_types ORDER BY name')
        results = cursor.fetchall()
        conn.close()
        return [r['name'] for r in results]

    def get_switch_os_types(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM switch_os_types ORDER BY name')
        results = cursor.fetchall()
        conn.close()
        return [r['name'] for r in results]

    def get_template_fields(self, template_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM template_fields WHERE template_id = ?', (template_id,))
        fields = cursor.fetchall()
        conn.close()
        return [dict(f) for f in fields]

    # Metadata management
    def add_host_type(self, name, description=''):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO host_types (name, description) VALUES (?, ?)', (name, description))
        conn.commit()
        conn.close()

    def remove_host_type(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM host_types WHERE name = ?', (name,))
        conn.commit()
        conn.close()

    def add_port_type(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO port_types (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()

    def remove_port_type(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM port_types WHERE name = ?', (name,))
        conn.commit()
        conn.close()

    def add_switch_os_type(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO switch_os_types (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()

    def remove_switch_os_type(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM switch_os_types WHERE name = ?', (name,))
        conn.commit()
        conn.close()

    # Template versioning methods
    def get_template_versions(self, template_id):
        """Get all versions for a template"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM template_versions
            WHERE template_id = ?
            ORDER BY version ASC
        ''', (template_id,))
        versions = cursor.fetchall()
        conn.close()
        return [dict(v) for v in versions]

    def get_template_version(self, template_id, version):
        """Get a specific version of a template with template metadata"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, tv.version, tv.version_name, tv.version_description, tv.template_content, tv.is_active, tv.updated_at as version_updated_at
            FROM templates t
            JOIN template_versions tv ON t.id = tv.template_id
            WHERE tv.template_id = ? AND tv.version = ?
        ''', (template_id, version))
        version_data = cursor.fetchone()
        conn.close()
        return dict(version_data) if version_data else None

    def create_template_version(self, template_id, template_content, version_name, version_description=''):
        """Create a new version for a template"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get the next version number
            cursor.execute('SELECT MAX(version) as max_ver FROM template_versions WHERE template_id = ?', (template_id,))
            result = cursor.fetchone()
            next_version = (result['max_ver'] or 0) + 1

            # Create new version
            cursor.execute('''
                INSERT INTO template_versions (template_id, version, version_name, version_description, template_content, is_active)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (template_id, next_version, version_name, version_description, template_content))

            conn.commit()
            return next_version
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_template_version(self, template_id, version, **kwargs):
        """Update a specific version (name, description, content)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            allowed_fields = ['version_name', 'version_description', 'template_content']
            updates = []
            values = []

            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(f'{key} = ?')
                    values.append(value)

            if updates:
                updates.append('updated_at = ?')
                values.append(datetime.now())
                values.append(template_id)
                values.append(version)
                query = f"UPDATE template_versions SET {', '.join(updates)} WHERE template_id = ? AND version = ?"
                cursor.execute(query, values)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_template_version(self, template_id, version):
        """Delete a specific version (cannot delete active version)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check if this is the active version
            cursor.execute('SELECT active_version FROM templates WHERE id = ?', (template_id,))
            template = cursor.fetchone()

            if template and template['active_version'] == version:
                raise ValueError('Cannot delete the active version. Please set another version as active first.')

            # Check if it's the only version
            cursor.execute('SELECT COUNT(*) as count FROM template_versions WHERE template_id = ?', (template_id,))
            count_result = cursor.fetchone()

            if count_result['count'] <= 1:
                raise ValueError('Cannot delete the only version. Templates must have at least one version.')

            cursor.execute('DELETE FROM template_versions WHERE template_id = ? AND version = ?', (template_id, version))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def set_active_version(self, template_id, version):
        """Set a version as the active/primary version"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Verify version exists
            cursor.execute('SELECT id FROM template_versions WHERE template_id = ? AND version = ?', (template_id, version))
            if not cursor.fetchone():
                raise ValueError(f'Version {version} not found for template {template_id}')

            # Update active version in templates table
            cursor.execute('UPDATE templates SET active_version = ?, updated_at = ? WHERE id = ?',
                         (version, datetime.now(), template_id))

            # Update is_active flags in template_versions
            cursor.execute('UPDATE template_versions SET is_active = 0 WHERE template_id = ?', (template_id,))
            cursor.execute('UPDATE template_versions SET is_active = 1 WHERE template_id = ? AND version = ?',
                         (template_id, version))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
