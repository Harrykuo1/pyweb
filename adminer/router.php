<?php

// Route even /adminer.php through the same authentication customization.
$webPassword = getenv('SQLITE_WEB_PASSWORD');
if ($webPassword === false || $webPassword === '' || !is_readable('/run/secrets/.postgres-password')) {
    http_response_code(503);
    exit('資料庫管理介面尚未設定完成。');
}

function adminer_object() {
    require_once '/opt/pyweb-adminer/login.php';
    return new Adminer\Plugins([new PywebAdminerLogin()]);
}

require '/var/www/html/adminer.php';
