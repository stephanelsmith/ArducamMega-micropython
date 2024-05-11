

import binascii

with open('image.txt', 'rb') as f:
    with open('image.jpg', 'wb') as j:
        j.write(binascii.a2b_base64(f.read()))
