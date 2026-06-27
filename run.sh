docker run -d -p 3102:8080 \
  --restart unless-stopped \
  --name wattscheduler \
  --network hermes-net \
  -v /data/wattscheduler:/app/data:rw \
  -e LOGO_LINK_URL \
  wattscheduler
