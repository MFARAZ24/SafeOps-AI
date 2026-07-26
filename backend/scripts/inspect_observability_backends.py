from app.observability.clients import (
    JaegerClient,
    ObservabilityBackendError,
    PrometheusClient,
)

from app.core.config import get_settings


def main() -> None:
    """Inspect available Prometheus and Jaeger data."""

    settings = get_settings()

    prometheus = PrometheusClient(
        settings.prometheus_base_url,
        timeout_seconds=(
            settings.observability_timeout_seconds
        ),
    )

    jaeger = JaegerClient(
        settings.jaeger_base_url,
        timeout_seconds=(
            settings.observability_timeout_seconds
        ),
    )

    try:
        print("PROMETHEUS")
        print("=" * 60)

        up_result = prometheus.query(
            "up"
        )

        print(
            "Result type:",
            up_result.result_type,
        )

        print(
            "Sample count:",
            up_result.sample_count,
        )

        for sample in up_result.samples[:10]:
            print(
                sample.metric,
                "value=",
                sample.value,
            )

        print()
        print("JAEGER")
        print("=" * 60)

        services = jaeger.list_services()

        print(
            "Service count:",
            services.service_count,
        )

        for service in services.services:
            print("-", service)

    except ObservabilityBackendError as exc:
        print(
            "Observability backend error:",
            exc,
        )

        raise SystemExit(1) from exc

    finally:
        prometheus.close()
        jaeger.close()


if __name__ == "__main__":
    main()