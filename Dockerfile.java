FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
COPY recommend-common/pom.xml recommend-common/
COPY recommend-repository/pom.xml recommend-repository/
COPY recommend-rpc/pom.xml recommend-rpc/
COPY recommend-strategy/pom.xml recommend-strategy/
COPY recommend-pipeline/pom.xml recommend-pipeline/
COPY recommend-api/pom.xml recommend-api/
RUN mvn dependency:go-offline -q
COPY . .
RUN mvn package -pl recommend-api -am -DskipTests -q

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=builder /build/recommend-api/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-Dmybatis-plus.network-check=false", "-jar", "app.jar"]
