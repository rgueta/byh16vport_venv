#!/usr/bin/env python3
import sqlite3
import cmd
import sys
from tabulate import tabulate
import json
import os


class SQLiteCLI(cmd.Cmd):
    intro = "🔍 SQLite Interactive Shell (type 'help' for commands)\n"
    prompt = "sqlite> "

    def __init__(self, db_path="vport.db"):
        super().__init__()
        self.db_path = db_path
        self.conn = None
        self.connect_db()

    def connect_db(self):
        """Conectar a la base de datos"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"✅ Conectado a: {self.db_path}")
        except Exception as e:
            print(f"❌ Error conectando: {e}")

    def do_find(self, arg):
        """Buscar documentos: find <tabla> [where campo=valor] [limit n]"""
        try:
            args = arg.split()
            if not args:
                print("❌ Uso: find <tabla> [where campo=valor] [limit n]")
                return

            table = args[0]
            where_clause = ""
            limit_clause = ""

            # Parsear argumentos
            i = 1
            while i < len(args):
                if args[i] == "where" and i + 1 < len(args):
                    where_clause = f"WHERE {args[i + 1]}"
                    i += 2
                elif args[i] == "limit" and i + 1 < len(args):
                    limit_clause = f"LIMIT {args[i + 1]}"
                    i += 2
                else:
                    i += 1

            # Construir query
            query = f"SELECT * FROM {table} {where_clause} {limit_clause}"
            cursor = self.conn.execute(query)

            # Obtener datos
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            if data:
                print(f"📊 {len(data)} documentos en {table}:")
                print(tabulate(data, headers=columns, tablefmt="grid"))
            else:
                print("📭 No se encontraron documentos")

        except Exception as e:
            print(f"❌ Error: {e}")

    def do_show(self, arg):
        """Mostrar tablas: show tables"""
        if arg.strip() == "tables":
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
            tables = cursor.fetchall()
            print("📋 Tablas:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("❌ Uso: show tables")

    def do_count(self, arg):
        """Contar documentos: count <tabla> [where campo=valor]"""
        try:
            args = arg.split()
            if not args:
                print("❌ Uso: count <tabla> [where campo=valor]")
                return

            table = args[0]
            where_clause = ""

            if len(args) > 2 and args[1] == "where":
                where_clause = f"WHERE {args[2]}"

            cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table} {where_clause}")
            count = cursor.fetchone()[0]
            print(f"📊 {table}: {count} documentos")

        except Exception as e:
            print(f"❌ Error: {e}")

    def do_insert(self, arg):
        """Insertar documento: insert <tabla> campo1=valor1 campo2=valor2"""
        try:
            args = arg.split()
            if len(args) < 2:
                print("❌ Uso: insert <tabla> campo1=valor1 campo2=valor2")
                return

            table = args[0]
            columns = []
            values = []

            for pair in args[1:]:
                if "=" in pair:
                    col, val = pair.split("=", 1)
                    columns.append(col)
                    # Intentar convertir a número si es posible
                    try:
                        if "." in val:
                            values.append(float(val))
                        else:
                            values.append(int(val))
                    except ValueError:
                        values.append(val)
                else:
                    print(f"⚠️ Ignorando argumento inválido: {pair}")

            if not columns:
                print("❌ No hay campos válidos para insertar")
                return

            placeholders = ", ".join(["?" for _ in values])
            columns_str = ", ".join(columns)

            query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
            self.conn.execute(query, values)
            self.conn.commit()
            print("✅ Documento insertado")

        except Exception as e:
            print(f"❌ Error: {e}")

    def do_delete(self, arg):
        """Eliminar documentos: delete <tabla> where campo=valor"""
        try:
            args = arg.split()
            if len(args) < 3 or args[1] != "where":
                print("❌ Uso: delete <tabla> where campo=valor")
                return

            table = args[0]
            where_condition = " ".join(args[2:])

            # Primero contar cuántos se eliminarán
            cursor = self.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where_condition}"
            )
            count = cursor.fetchone()[0]

            if count == 0:
                print("📭 No hay documentos que coincidan")
                return

            confirm = input(f"⚠️ ¿Eliminar {count} documentos? (y/N): ")
            if confirm.lower() == "y":
                self.conn.execute(f"DELETE FROM {table} WHERE {where_condition}")
                self.conn.commit()
                print(f"✅ {count} documentos eliminados")
            else:
                print("❌ Eliminación cancelada")

        except Exception as e:
            print(f"❌ Error: {e}")

    def do_clean(self, arg):
        """Eliminar documentos: delete <tabla> where campo=valor"""
        try:
            args = arg.split()
            if len(args) == 0:
                print("❌ Uso: delete <tabla> ")
                return

            table = args[0]

            # Primero contar cuántos se eliminarán
            cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            if count == 0:
                print("📭 No hay documentos que coincidan")
                return

            confirm = input(f"⚠️ ¿Eliminar {count} documentos? (y/N): ")
            if confirm.lower() == "y":
                self.conn.execute(f"DELETE FROM {table}")
                self.conn.commit()
                print(f"✅ {count} documentos eliminados")
            else:
                print("❌ Eliminación cancelada")

        except Exception as e:
            print(f"❌ Error: {e}")

    def do_exit(self, arg):
        """Salir del CLI: exit"""
        print("👋 ¡Hasta luego!")
        if self.conn:
            self.conn.close()
        return True

    def default(self, line):
        """Ejecutar SQL directo"""
        try:
            if line.strip().lower().startswith("select"):
                cursor = self.conn.execute(line)
                data = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                if data:
                    print(tabulate(data, headers=columns, tablefmt="grid"))
                else:
                    print("📭 No hay resultados")
            else:
                cursor = self.conn.execute(line)
                self.conn.commit()
                print("✅ Comando ejecutado")

        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "vport.db"

    if not os.path.exists(db_path):
        print(f"❌ La base de datos '{db_path}' no existe")
        return

    try:
        SQLiteCLI(db_path).cmdloop()
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")


if __name__ == "__main__":
    main()
