"""Exercise the shipped Adminer image against disposable PostgreSQL data."""

import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
WEB_PASSWORD = "test-web-<&$-password"
DB_PASSWORD = "test-database-password"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


class AdminerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefix = "pyweb-adminer-test-" + uuid.uuid4().hex[:10]
        cls.containers = []
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.cleanup)
        directory = Path(cls.temp.name)
        directory.chmod(0o755)
        credential = directory / ".postgres-password"
        credential.write_text(DB_PASSWORD + "\n")
        credential.chmod(0o644)
        docker("build", "-q", "-t", cls.prefix, str(ROOT / "adminer"))
        docker("network", "create", cls.prefix)
        cls.pg = cls.prefix + "-postgres"
        cls.containers.append(cls.pg)
        docker(
            "run",
            "-d",
            "--name",
            cls.pg,
            "--network",
            cls.prefix,
            "--network-alias",
            "postgres",
            "-e",
            "POSTGRES_USER=pyweb",
            "-e",
            "POSTGRES_DB=pyweb",
            "-e",
            "POSTGRES_PASSWORD=" + DB_PASSWORD,
            "--tmpfs",
            "/var/lib/postgresql/data",
            "postgres:17",
        )
        for _ in range(100):
            ready = (
                subprocess.run(
                    ["docker", "exec", cls.pg, "pg_isready", "-U", "pyweb"],
                    capture_output=True,
                ).returncode
                == 0
            )
            if ready:
                try:
                    docker(
                        "exec",
                        cls.pg,
                        "psql",
                        "-U",
                        "pyweb",
                        "-d",
                        "pyweb",
                        "-c",
                        "CREATE TABLE adminer_probe (id integer primary key, note text);",
                    )
                    break
                except RuntimeError:
                    pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Disposable PostgreSQL failed to start")
        cls.base = cls.start_adminer("web", WEB_PASSWORD)
        cls.disabled = cls.start_adminer("disabled", "")
        cls.missing_secret = cls.start_adminer("missing-secret", WEB_PASSWORD, False)

    @classmethod
    def start_adminer(cls, suffix, password, mount=True):
        name = cls.prefix + "-" + suffix
        cls.containers.append(name)
        args = [
            "run",
            "-d",
            "--name",
            name,
            "--network",
            cls.prefix,
            "-p",
            "127.0.0.1::8080",
            "-e",
            "SQLITE_WEB_PASSWORD=" + password,
        ]
        if mount:
            args += ["-v", cls.temp.name + ":/run/secrets:ro"]
        docker(*args, cls.prefix)
        port = docker("port", name, "8080/tcp")
        base = "http://" + port
        for _ in range(100):
            try:
                urllib.request.urlopen(base, timeout=1).close()
                return base
            except urllib.error.HTTPError:
                return base
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Adminer did not start")

    @classmethod
    def cleanup(cls):
        for container in reversed(cls.containers):
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        subprocess.run(["docker", "network", "rm", cls.prefix], capture_output=True)
        subprocess.run(["docker", "image", "rm", cls.prefix], capture_output=True)
        cls.temp.cleanup()

    def client(self):
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(self, client, path="/", data=None, base=None):
        encoded = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            response = client.open((base or self.base) + path, encoded, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read().decode(), response.url

    def token(self, body):
        match = re.search(r'name=[\'"]token[\'"] value=[\'"]([^\'"]+)', body)
        self.assertIsNotNone(match, "Adminer must provide a CSRF token")
        return match.group(1)

    def login(self, password=WEB_PASSWORD, path="/", **overrides):
        client = self.client()
        status, body, _ = self.request(client, path)
        self.assertEqual(status, 200)
        fields = {
            "driver": "pgsql",
            "server": "postgres",
            "username": "pyweb",
            "db": "pyweb",
            "password": password,
        }
        fields.update(overrides)
        data = {"auth[" + key + "]": value for key, value in fields.items()}
        data["token"] = self.token(body)
        return client, self.request(client, path, data)

    def test_login_and_sql_write_read_logout(self):
        client, (status, body, url) = self.login()
        self.assertEqual(status, 200)
        self.assertIn("adminer_probe", body)
        self.assertNotIn(DB_PASSWORD, body)
        path = url.removeprefix(self.base) + "&sql="
        status, body, _ = self.request(client, path)
        status, body, _ = self.request(
            client,
            path,
            {
                "token": self.token(body),
                "query": "INSERT INTO adminer_probe VALUES (1, 'adminer-insert-ok'); SELECT * FROM adminer_probe;",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("adminer-insert-ok", body)
        result = docker(
            "exec",
            self.pg,
            "psql",
            "-U",
            "pyweb",
            "-d",
            "pyweb",
            "-Atc",
            "SELECT note FROM adminer_probe WHERE id=1",
        )
        self.assertEqual(result, "adminer-insert-ok")
        status, body, _ = self.request(
            client, path, {"token": self.token(body), "logout": "1"}
        )
        self.assertIn("auth[password]", body)
        status, body, _ = self.request(client, path)
        self.assertEqual(status, 403)
        self.assertNotIn("adminer-insert-ok", body)

    def test_wrong_empty_and_database_password_rejected(self):
        for password in ["wrong-password", "", DB_PASSWORD]:
            with self.subTest(password_kind="empty" if not password else "incorrect"):
                _, (status, body, _) = self.login(password)
                self.assertEqual(status, 403)
                self.assertNotIn("adminer_probe", body)
                self.assertNotIn(DB_PASSWORD, body)

    def test_server_user_database_and_driver_cannot_be_overridden(self):
        for fields in [
            {"server": "example.invalid"},
            {"username": "postgres"},
            {"db": "postgres"},
            {"driver": "server"},
        ]:
            with self.subTest(fields=fields):
                _, (status, body, _) = self.login(**fields)
                self.assertEqual(status, 403)
                self.assertNotIn("adminer_probe", body)
                self.assertNotIn(DB_PASSWORD, body)

    def test_direct_php_path_cannot_bypass_password(self):
        _, (status, body, _) = self.login(DB_PASSWORD, path="/adminer.php")
        self.assertEqual(status, 403)
        self.assertNotIn("adminer_probe", body)
        _, (status, body, _) = self.login(path="/adminer.php")
        self.assertEqual(status, 200)
        self.assertIn("adminer_probe", body)

    def test_login_requires_csrf_token(self):
        client = self.client()
        self.request(client)
        status, body, _ = self.request(
            client,
            data={
                "auth[driver]": "pgsql",
                "auth[server]": "postgres",
                "auth[username]": "pyweb",
                "auth[db]": "pyweb",
                "auth[password]": WEB_PASSWORD,
            },
        )
        self.assertIn("auth[password]", body)
        self.assertNotIn("adminer_probe", body)

    def test_missing_configuration_fails_closed(self):
        for base in [self.disabled, self.missing_secret]:
            status, body, _ = self.request(self.client(), base=base)
            self.assertEqual(status, 503)
            self.assertNotIn("adminer_probe", body)

    def test_compose_publishes_only_loopback_management_ports(self):
        # A clean CI checkout has no .env. Keep the service env_file fixture
        # separate from the developer's configuration and database files.
        with tempfile.TemporaryDirectory(prefix="pyweb-compose-test-") as directory:
            project = Path(directory)
            (project / "docker-compose.yml").write_bytes(
                (ROOT / "docker-compose.yml").read_bytes()
            )
            env_file = project / ".env"
            env_file.write_text("SESSION_SECRET=test-only\n")
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    str(env_file),
                    "config",
                    "--format",
                    "json",
                ],
                cwd=project,
                env={
                    **os.environ,
                    "SQLITE_WEB_PASSWORD": WEB_PASSWORD,
                    "ONLYOFFICE_JWT_SECRET": "test",
                },
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        services = json.loads(result.stdout)["services"]
        for name, port in [("postgres", 5432), ("adminer", 8119)]:
            self.assertEqual(len(services[name]["ports"]), 1)
            mapping = services[name]["ports"][0]
            self.assertEqual(mapping["host_ip"], "127.0.0.1")
            self.assertEqual(str(mapping["published"]), str(port))
        # Compose escapes dollars when serializing an interpolated configuration.
        self.assertEqual(
            services["adminer"]["environment"]["SQLITE_WEB_PASSWORD"].replace(
                "$$", "$"
            ),
            WEB_PASSWORD,
        )
        self.assertNotIn("sqlite-web", services)


if __name__ == "__main__":
    unittest.main(verbosity=2)
