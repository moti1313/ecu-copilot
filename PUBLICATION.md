# Development history and recorded experiments

This public repository retains the technical development history of ECU Copilot.
Private planning and preparation documents were removed from the history before
publication. Commits made empty by that removal were pruned. Authors, retained
commit dates and their chronological development order were preserved. A separate
publication commit adds the reader-facing documentation, MIT license and registry
configuration for this repository.

Filtering changes commit IDs. This is a derived public history, not a claim that
the original experiments ran on these rewritten commits or on a clean checkout.
Original commit references inside the result documents remain historical records.
The run-4 archive recorded a dirty working tree without a complete historical
diff, so reconstructing its exact code state is limited independently of this
publication. The reported benchmark results have not been changed.

The raw experiment archives are not part of this public repository. Five
archive-dependent tests skip when those archives are absent; the remaining
offline tests use mocked model clients and require no model-provider API key.
New paid evaluations can produce different outcomes from the recorded runs.

The earlier development release tags and their images are not advertised as
public releases of this repository. Public releases use this repository's own
image namespace and must pass its release checks before publication. Building
the source locally does not depend on an existing registry release.

All test data, technical specifications and component documents are synthetic.
The runtime has no connection to a physical production line. The source and
project documentation are distributed under the [MIT License](LICENSE).
