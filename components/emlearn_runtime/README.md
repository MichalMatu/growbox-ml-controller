# emlearn runtime subset

This component contains the narrow, header-only neural-network runtime required by the generated
Growbox model. Its public structures, activation functions, matrix traversal, and regression API
match `emlearn` commit `3a4053a60e53d79d42b9d359eba72cd5c07e4e6b`.

Only the dense-network API used by `EnvironmentModel.h` is included. Keeping this small compatibility
layer in-tree makes ESP-IDF and host builds deterministic and independent of network access. The
training/export pipeline continues to use the pinned Python `emlearn` package and verifies generated
predictions against committed golden vectors.

Upstream: `https://github.com/emlearn/emlearn`
License: MIT, see `LICENSE`.
