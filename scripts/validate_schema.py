#!/usr/bin/env python3
"""
Schema Architect Validator
Validates generated schema files for naming conventions, consistency, and completeness.

Usage: python3 validate_schema.py <output_directory>
"""

import os
import re
import sys
import hashlib
from pathlib import Path


class SchemaValidator:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.stats = {
            "sql_files": 0,
            "cypher_files": 0,
            "toml_files": 0,
            "rust_files": 0,
            "go_files": 0,
            "tables": 0,
            "indexes": 0,
            "constraints": 0,
        }

    def validate(self) -> bool:
        if not self.directory.exists():
            self.errors.append(f"Directory does not exist: {self.directory}")
            return False

        self._validate_sql_files()
        self._validate_cypher_files()
        self._validate_toml_files()
        self._validate_rust_files()
        self._validate_go_files()
        self._validate_migration_ordering()
        self._validate_cross_references()

        self._print_report()
        return len(self.errors) == 0

    def _validate_sql_files(self):
        for f in self.directory.rglob("*.sql"):
            self.stats["sql_files"] += 1
            content = f.read_text()

            # Check naming conventions
            tables = re.findall(r'CREATE TABLE\s+(\w+)', content, re.IGNORECASE)
            for table in tables:
                self.stats["tables"] += 1
                if table != table.lower():
                    self.errors.append(f"{f.name}: Table '{table}' must be lowercase snake_case")
                if not table.endswith('s') and table not in ('audit_log', 'schema_migrations'):
                    self.warnings.append(f"{f.name}: Table '{table}' should be plural")

            # Check for STRICT tables
            creates = re.findall(r'CREATE TABLE\s+\w+\s*\([^;]+\)', content, re.DOTALL)
            for create in creates:
                if 'STRICT' not in content[content.index(create):content.index(create)+len(create)+20]:
                    self.warnings.append(f"{f.name}: Consider using STRICT tables for type safety")

            # Check for missing indexes on foreign keys
            fks = re.findall(r'(\w+)\s+INTEGER\s+.*?REFERENCES\s+(\w+)', content, re.IGNORECASE)
            indexes = re.findall(r'CREATE INDEX\s+\w+\s+ON\s+\w+\((\w+)', content, re.IGNORECASE)
            for fk_col, ref_table in fks:
                self.stats["constraints"] += 1
                if fk_col not in indexes:
                    self.errors.append(f"{f.name}: Foreign key '{fk_col}' missing index")

            # Check for created_at/updated_at
            if 'CREATE TABLE' in content and 'schema_migrations' not in content:
                if 'created_at' not in content.lower():
                    self.warnings.append(f"{f.name}: Missing 'created_at' timestamp column")
                if 'updated_at' not in content.lower():
                    self.warnings.append(f"{f.name}: Missing 'updated_at' timestamp column")

            # Check for version column (optimistic locking)
            if 'CREATE TABLE' in content and 'schema_migrations' not in content and 'audit_log' not in content:
                if 'version' not in content.lower():
                    self.warnings.append(f"{f.name}: Consider adding 'version' column for optimistic locking")

            # Count indexes
            idx_count = len(re.findall(r'CREATE\s+(?:UNIQUE\s+)?INDEX', content, re.IGNORECASE))
            self.stats["indexes"] += idx_count

            # Check migration structure
            if f.parent.name == 'migrations':
                if '-- +migrate up' not in content:
                    self.errors.append(f"{f.name}: Missing '-- +migrate up' section")
                if '-- +migrate down' not in content:
                    self.errors.append(f"{f.name}: Missing '-- +migrate down' section")

    def _validate_cypher_files(self):
        for f in self.directory.rglob("*.cypher"):
            self.stats["cypher_files"] += 1
            content = f.read_text()

            # Check node label conventions (PascalCase)
            labels = re.findall(r':(\w+)\s*[{)]', content)
            for label in labels:
                if label[0].islower():
                    self.errors.append(f"{f.name}: Node label '{label}' must be PascalCase")

            # Check relationship type conventions (UPPER_SNAKE_CASE)
            rels = re.findall(r'\[:(\w+)', content)
            for rel in rels:
                if rel != rel.upper():
                    self.errors.append(f"{f.name}: Relationship '{rel}' must be UPPER_SNAKE_CASE")

            # Check property conventions (camelCase)
            props = re.findall(r'\.(\w+)\s', content)
            for prop in props:
                if '_' in prop and prop not in ('IS', 'NOT', 'NULL', 'UNIQUE', 'NODE', 'KEY'):
                    self.warnings.append(f"{f.name}: Property '{prop}' should be camelCase")

            # Check for IF NOT EXISTS on constraints
            constraints = re.findall(r'CREATE CONSTRAINT\s+(\w+)(?!\s+IF)', content)
            for c in constraints:
                self.warnings.append(f"{f.name}: Constraint '{c}' should use IF NOT EXISTS")

    def _validate_toml_files(self):
        for f in self.directory.rglob("*.toml"):
            self.stats["toml_files"] += 1
            content = f.read_text()

            # Check for TTL on cache namespaces
            if 'cache' in content.lower():
                sections = content.split('[namespaces.')
                for section in sections[1:]:
                    name = section.split(']')[0]
                    if 'cache' in name.lower() and 'ttl_seconds' not in section:
                        self.errors.append(f"{f.name}: Cache namespace '{name}' missing ttl_seconds")

            # Check key pattern format
            patterns = re.findall(r'pattern\s*=\s*"([^"]+)"', content)
            for pattern in patterns:
                if '.' in pattern or '/' in pattern:
                    self.errors.append(f"{f.name}: Key pattern '{pattern}' should use ':' separators")

    def _validate_rust_files(self):
        for f in self.directory.rglob("*.rs"):
            self.stats["rust_files"] += 1
            content = f.read_text()

            # Check for proper derives
            structs = re.findall(r'pub struct (\w+)', content)
            for s in structs:
                if 'FromRow' in content and 'Serialize' not in content:
                    self.warnings.append(f"{f.name}: Struct '{s}' has FromRow but missing Serialize")

            # Check for string concatenation in queries (SQL injection risk)
            if 'format!' in content and ('SELECT' in content or 'INSERT' in content):
                self.warnings.append(f"{f.name}: Potential SQL injection — use parameterized queries")

    def _validate_go_files(self):
        for f in self.directory.rglob("*.go"):
            self.stats["go_files"] += 1
            content = f.read_text()

            # Check for json tags on exported fields
            fields = re.findall(r'(\w+)\s+\w+\s+`', content)
            for field in fields:
                if field[0].isupper() and 'json:' not in content:
                    self.warnings.append(f"{f.name}: Field '{field}' may need json tag")

            # Check for context.Context in repo methods
            if 'Repo' in content and 'context.Context' not in content:
                self.warnings.append(f"{f.name}: Repository methods should accept context.Context")

    def _validate_migration_ordering(self):
        migrations_dir = self.directory / "migrations"
        if not migrations_dir.exists():
            return

        files = sorted(migrations_dir.glob("*.sql"))
        timestamps = []
        for f in files:
            match = re.match(r'(\d{14})_', f.name)
            if not match:
                self.errors.append(f"Migration '{f.name}' does not follow YYYYMMDDHHMMSS_name.sql format")
            else:
                ts = match.group(1)
                if ts in timestamps:
                    self.errors.append(f"Duplicate migration timestamp: {ts}")
                timestamps.append(ts)

        if timestamps != sorted(timestamps):
            self.errors.append("Migration timestamps are not in chronological order")

    def _validate_cross_references(self):
        """Check that UUIDs referenced across databases are consistent."""
        sql_tables = set()
        for f in self.directory.rglob("*.sql"):
            content = f.read_text()
            tables = re.findall(r'CREATE TABLE\s+(\w+)', content, re.IGNORECASE)
            sql_tables.update(tables)

        cypher_labels = set()
        for f in self.directory.rglob("*.cypher"):
            content = f.read_text()
            labels = re.findall(r'FOR \((?:\w+):(\w+)\)', content)
            cypher_labels.update(labels)

        # Check that Neo4j labels correspond to SQLite tables
        for label in cypher_labels:
            expected_table = re.sub(r'(?<!^)(?=[A-Z])', '_', label).lower() + 's'
            if expected_table not in sql_tables and label.lower() + 's' not in sql_tables:
                self.warnings.append(
                    f"Neo4j label '{label}' has no corresponding SQLite table "
                    f"(expected '{expected_table}')"
                )

    def _print_report(self):
        print("=" * 60)
        print("  Schema Architect — Validation Report")
        print("=" * 60)
        print()
        print("  Files scanned:")
        for key, val in self.stats.items():
            if val > 0:
                print(f"    {key.replace('_', ' ').title()}: {val}")
        print()

        if self.errors:
            print(f"  ERRORS ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ✗ {e}")
            print()

        if self.warnings:
            print(f"  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠ {w}")
            print()

        if not self.errors and not self.warnings:
            print("  ✓ All checks passed — schema is clean!")
        elif not self.errors:
            print(f"  ✓ No errors. {len(self.warnings)} warning(s) to review.")
        else:
            print(f"  ✗ {len(self.errors)} error(s) must be fixed.")
        print()


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 validate_schema.py <output_directory>")
        print("  Validates generated schema files for naming, consistency, and completeness.")
        sys.exit(1)

    validator = SchemaValidator(sys.argv[1])
    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
