#!/usr/bin/env python3
"""
Test Setup Script
==================
Verifies that all components are properly configured.
"""

import sys
import os
from pathlib import Path


def check_python_version():
    """Check Python version is 3.10+"""
    print("Checking Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} (need 3.10+)")
        return False


def check_dependencies():
    """Check required packages are installed."""
    print("\nChecking dependencies...")
    
    packages = [
        ("rich", "rich"),
        ("yaml", "pyyaml"),
        ("pydantic", "pydantic"),
        ("tiktoken", "tiktoken"),
        ("dotenv", "python-dotenv"),
    ]
    
    optional = [
        ("openai", "openai"),
        ("anthropic", "anthropic"),
    ]
    
    all_ok = True
    
    for module_name, package_name in packages:
        try:
            __import__(module_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            print(f"  ❌ {package_name} - pip install {package_name}")
            all_ok = False
    
    print("\nOptional dependencies (need at least one):")
    optional_ok = False
    for module_name, package_name in optional:
        try:
            __import__(module_name)
            print(f"  ✅ {package_name}")
            optional_ok = True
        except ImportError:
            print(f"  ⚪ {package_name} - pip install {package_name}")
    
    if not optional_ok:
        print("  ⚠️  Need at least one LLM provider (openai or anthropic)")
    
    return all_ok


def check_tshark():
    """Check if tshark is installed."""
    print("\nChecking Tshark...", end=" ")
    
    import shutil
    
    tshark = shutil.which("tshark")
    if tshark:
        print(f"✅ Found at {tshark}")
        return True
    
    # Check Windows paths
    windows_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
    ]
    
    for path in windows_paths:
        if Path(path).exists():
            print(f"✅ Found at {path}")
            return True
    
    print("❌ Not found")
    print("  Install from: https://www.wireshark.org/download.html")
    return False


def check_api_keys():
    """Check for API key configuration."""
    print("\nChecking API keys...")
    
    # Try loading .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    has_key = False
    
    if openai_key and not openai_key.startswith("sk-your"):
        print("  ✅ OPENAI_API_KEY configured")
        has_key = True
    else:
        print("  ⚪ OPENAI_API_KEY not set")
    
    if anthropic_key and not anthropic_key.startswith("sk-ant-your"):
        print("  ✅ ANTHROPIC_API_KEY configured")
        has_key = True
    else:
        print("  ⚪ ANTHROPIC_API_KEY not set")
    
    if not has_key:
        print("  ⚠️  Need at least one API key in .env")
        print("     Copy .env.example to .env and add your key")
    
    return has_key


def check_config():
    """Check configuration file."""
    print("\nChecking configuration...", end=" ")
    
    config_path = Path("config.yaml")
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            print(f"✅ config.yaml loaded")
            print(f"     Current model: {config.get('current_model', 'not set')}")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    else:
        print("❌ config.yaml not found")
        return False


def check_project_structure():
    """Check project files exist."""
    print("\nChecking project structure...")
    
    required_files = [
        "agent.py",
        "config.yaml",
        "requirements.txt",
        "src/__init__.py",
        "src/state_manager.py",
        "src/toolbox.py",
        "src/llm_interface.py",
        "src/ui.py",
        "src/utils.py",
    ]
    
    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            all_ok = False
    
    return all_ok


def main():
    """Run all checks."""
    print("=" * 60)
    print("PCAP Forensic Analysis Agent - Setup Verification")
    print("=" * 60)
    
    results = {
        "Python": check_python_version(),
        "Dependencies": check_dependencies(),
        "Tshark": check_tshark(),
        "API Keys": check_api_keys(),
        "Config": check_config(),
        "Project Files": check_project_structure(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed and name not in ["API Keys"]:  # API keys can be added later
            all_pass = False
    
    print()
    if all_pass:
        print("🎉 All checks passed! Ready to analyze PCAPs.")
        print("\nRun: python agent.py --pcap <your_file.pcap>")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

