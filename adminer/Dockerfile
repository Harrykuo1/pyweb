FROM adminer:6.1.1-standalone

COPY router.php login.php display.php display.js /opt/pyweb-adminer/
USER 1000:1000
ENTRYPOINT ["docker-php-entrypoint"]
CMD ["php", "-S", "0.0.0.0:8080", "-t", "/var/www/html", "/opt/pyweb-adminer/router.php"]
