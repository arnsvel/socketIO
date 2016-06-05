# Setup

# create a virtual env to install libraries, system wide
virtualenv --system-site-packages venv

# enable virtual env
source venv/bin/activate

# install all requirements to virtual env
pip install -r requirements.txt

# Install eventlet for
pip install eventlet

python app.py