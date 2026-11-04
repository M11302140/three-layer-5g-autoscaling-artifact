FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum* ./
COPY cmd ./cmd
COPY internal ./internal
ENV CGO_ENABLED=0
RUN go mod tidy && go build -ldflags="-s -w" -o /out/hhro-daemon ./cmd/hhro-daemon

FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/hhro-daemon /hhro-daemon
USER nonroot
EXPOSE 8080
ENTRYPOINT ["/hhro-daemon"]
