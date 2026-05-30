docker run -d -p 3102:8080 \
  --restart unless-stopped \
  --name wattscheduler \
  -v /data/wattscheduler:/app/default_cache:rw \
  wattscheduler
