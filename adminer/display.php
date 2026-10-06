<?php

final class PywebAdminerDisplay {
    public function head() {
        if (Adminer\DRIVER === 'pgsql') {
            echo Adminer\script(file_get_contents(__DIR__ . '/display.js'));
        }
    }
}
