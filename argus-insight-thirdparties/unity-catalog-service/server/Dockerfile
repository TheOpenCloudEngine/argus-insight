FROM unitycatalog/unitycatalog:v0.4.0
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

USER root

# Copy custom configuration
COPY hibernate.properties /home/unitycatalog/etc/conf/hibernate.properties
COPY server.properties /home/unitycatalog/etc/conf/server.properties

# Ensure correct ownership
RUN chown -R unitycatalog:unitycatalog /home/unitycatalog/etc/conf/

USER unitycatalog
WORKDIR /home/unitycatalog
EXPOSE 8080

CMD ["./bin/start-uc-server"]
