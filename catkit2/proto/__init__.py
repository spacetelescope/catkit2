import os
import sys

# This is HORRIBLE. Protoc produces files with absolute imports.
# This is apparently intended behaviour. I do not understand how
# protoc is supposed to work with multiple languages. This is
# a simple but horrible solution to absolute imports.
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
