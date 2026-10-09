import logging

# Clear any log handler previously set
logging.getLogger(__name__).addHandler(logging.NullHandler())