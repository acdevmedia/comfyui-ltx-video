# ACDEV LTX-2.5 Studio on Runpod Hub

[Deploy from Runpod Hub](https://console.runpod.io/hub/listing/acdevmedia/comfyui-ltx-video)

Choose the **Pod** deployment option for direct browser access through Connect → HTTP 8000. The Hub configuration also supports Serverless **Load Balancer** endpoints. The ComfyUI browser, uploads, video downloads and WebSockets are proxied to the existing ComfyUI service. Queued generation jobs are not implemented.

Use one A100 80 GB GPU and a 200 GB container disk. Set HF_TOKEN from a Runpod Secret containing a Hugging Face read token and accept all model terms described in the [repository README](https://github.com/acdevmedia/comfyui-ltx-video#readme). First startup downloads tens of GB of models. Secrets and model weights are never baked into the image.

For a Serverless browser session, keep exactly one worker active (minimum and maximum 1) so uploads, queue/history and WebSockets stay on the same worker. Access requires Runpod endpoint authentication; use an authenticated client/proxy capable of sending the Authorization header for browser HTTP and WebSocket requests. Direct browser access is simplest with the Pod option. Download outputs before deleting a Pod or worker; container storage is temporary.

The Hub image uses `.runpod/Dockerfile` with the repository root as build context. The original root Dockerfile remains available for the existing Pod template. PORT=8000 serves ComfyUI; PORT_HEALTH=8001 serves /ping, returning 503 until ComfyUI /system_stats reports devices. The wrapper exits if the original startup process exits and forwards termination to its process group.

The Hub test payload `{"healthcheck": true}` is accepted at POST / and POST /runsync. It checks ComfyUI readiness after model provisioning; it does not claim to validate video generation. `tests.json` references the Runpod Secret HUGGINGFACE_TOKEN. Ensure that secret is available to the Hub test runner; if Hub does not resolve account secrets for tests, a private test credential must be configured in the console. Never replace the reference with a token in Git. Hub-side LB test dispatch and gated model access require validation by Runpod's build/test service.
