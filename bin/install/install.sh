#!/bin/bash
# This file is part of Open-Capture Runtime

# Open-Capture for Invoices is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Open-Capture is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Open-Capture for Invoices. If not, see <https://www.gnu.org/licenses/gpl-3.0.html>.

# @dev : Nathan Cheval <nathan.cheval@outlook.fr>

if [ "$EUID" -ne 0 ]; then
    echo "install.sh needed to be launch by user with root privileges"
    exit 1
fi

defaultPath=/var/www/html/opencapture_runtime/
imageMagickPolicyFile=/etc/ImageMagick-6/policy.xml

user=$(who am i | awk '{print $1}')
group=www-data

if [ -z "$user" ]; then
    printf "The user variable is empty. Please fill it with your desired user : "
    read -r user
    if [ -z "$user" ]; then
        echo 'User remain empty, exiting...'
        exit
    fi
fi

xargs -a apt-requirements.txt apt install -y
python3 -m pip install --upgrade setuptools
python3 -m pip install --upgrade pip
python3 -m pip install -r pip-requirements.txt

cd $defaultPath || exit 1
find . -name ".gitkeep" -delete

####################
# Create the Apache service for backend
touch /etc/apache2/sites-available/opencapture_runtime.conf
su -c "cat > /etc/apache2/sites-available/opencapture_runtime.conf << EOF
<VirtualHost *:80>
    ServerName localhost
    DocumentRoot $defaultPath
    WSGIDaemonProcess opencapture_runtime user=$user group=$group threads=5
    WSGIScriptAlias /runtime $defaultPath/opencapture.wsgi

    <Directory $defaultPath>
        AllowOverride All
        WSGIProcessGroup opencapture_runtime
        WSGIApplicationGroup %{GLOBAL}
        WSGIPassAuthorization On
        Order deny,allow
        Allow from all
        Require all granted
    </Directory>
</VirtualHost>
EOF"

####################
# Disable default Apache2 configuration
# Enable OpenCapture configuration
# Disable default configuration to avoid conflict
# And restart Apache
a2ensite opencapture_runtime.conf
a2dissite 000-default.conf
systemctl restart apache2

####################
# Copy file from default one
cp $defaultPath/config/mail.ini.default $defaultPath/config/mail.ini

####################
# Fix the rights after root launch to avoid permissions issues
chmod -R 775 $defaultPath
chmod -R g+s $defaultPath
chown -R "$user":"$group" $defaultPath