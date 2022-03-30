Open-Capture is a free and Open Source software under GNU General Public License v3.0.

# Installation
## Install Open-Capture for Invoices

Please, do not run the following command as root and create a specific user for Open-Capture For Invoices.

    sudo mkdir -p /var/www/html/opencapture_runtime/ && sudo chmod -R 775 /var/www/html/opencapture_runtime/ && sudo chown -R $(whoami):$(whoami) /var/www/html/opencapture_runtime/
    sudo apt install git
    git clone https://github.com/edissyum/opencapture_runtime/ /var/www/html/opencapture_runtime/
    cd /var/www/html/opencapture_runtime/bin/install/

The `./install.sh` command create the service using `www-data` group (apache2 default group) and the current user.

`Please avoid using root user`

    chmod u+x install.sh
    sudo ./install.sh

It will install all the needed dependencies and install Tesseract V4.X.X with French and English locale. If you need more locales, just do :

    sudo apt install tesseract-ocr-<langcode>

Here is a list of all available languages code : https://www.macports.org/ports.php?by=name&substr=tesseract-

If you plan to upload large invoices from the interface, using the upload form, you had to modify ImageMagick some settings.
Go to following file : `/etc/ImageMagick-6/policy.xml` and increase the value (to `4GiB` for exemple) of the following line :

      <policy domain="resource" name="disk" value="1GiB"/>

Then restart apache

    sudo systemctl restart apache2