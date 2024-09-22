#!/bin/bash

# Install Rust (for building tokenizers and other Rust-based dependencies)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Install other project dependencies
pip install -r requirements.txt
