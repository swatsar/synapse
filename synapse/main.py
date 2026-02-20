from synapse.core.models import PROTOCOL_VERSION, SPEC_VERSION

def main():
    print("Synapse Initialized")
    print(f"Protocol Version: {PROTOCOL_VERSION}")
    print(f"Spec Version: {SPEC_VERSION}")

if __name__ == "__main__":
    main()
