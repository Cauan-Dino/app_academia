import httpx2

# Um cliente por processo. O pool separa as conexões por host automaticamente,
# então o mesmo objeto serve a Expo e a Meta sem misturá-las.
cliente_http = httpx2.AsyncClient(
    timeout=10.0,               # tempo máximo de uma requisição inteira
    limits=httpx2.Limits(
        max_connections=100,          # teto total
        max_keepalive_connections=20, # quantas ociosas ficam guardadas
        keepalive_expiry=5.0,         # segundos que cada ociosa sobrevive
    ),
)
