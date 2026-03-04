openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 30 -nodes; openssl s_server -quiet -key key.pem -cert cert.pem -port 9001
# openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 30 -nodes; stty raw -echo; openssl s_server -quiet -key key.pem -cert cert.pem -port 9001 -www

