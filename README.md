example .env:
```
USERNAME=user@email.com
PASSWORD=password
PROXY=https://user:password@proxy.com:89
TZ=America/New_York
```


example run command:
```
docker run -d -p 80:80 --env-file .env --name nhltv nhltv-unleashed
```
