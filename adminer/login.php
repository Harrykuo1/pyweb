<?php

final class PywebAdminerLogin {
    private function authorized(): bool {
        $expected = getenv('SQLITE_WEB_PASSWORD');
        $password = Adminer\get_password();
        return is_string($expected) && $expected !== ''
            && is_string($password) && hash_equals($expected, $password)
            && Adminer\DRIVER === 'pgsql' && Adminer\SERVER === 'postgres'
            && ($_GET['username'] ?? '') === 'pyweb'
            && Adminer\DB === 'pyweb';
    }

    public function credentials(): array {
        // Never release the database credential to an unverified login or another host.
        if (!$this->authorized()) {
            return ['127.0.0.1:1', 'invalid', 'invalid'];
        }
        return ['postgres', 'pyweb', trim(file_get_contents('/run/secrets/.postgres-password'))];
    }

    public function login($login, $password): bool {
        return $this->authorized();
    }

    public function loginFormField($name, $heading, $value): string {
        $fixed = ['driver' => 'pgsql', 'server' => 'postgres', 'username' => 'pyweb', 'db' => 'pyweb'];
        if (isset($fixed[$name])) {
            return '<input type="hidden" name="auth[' . $name . ']" value="' . $fixed[$name] . '">';
        }
        return $heading . $value;
    }

    public function permanentLogin($create = false): string {
        return '';
    }
}
