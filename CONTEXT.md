# Bag Mode

Bag Mode keeps a MacBook operational with its lid closed while preserving the
settings needed to return the machine to its prior state.

## Language

**Service**:
The complete Bag Mode facility managed through the CLI.
_Avoid_: Daemon, process

**Controller**:
The single privileged process that observes the lid and battery and applies
Bag Mode settings.
_Avoid_: Service, loop

**Controller session**:
One continuous period in which a controller owns captured settings.
_Avoid_: Run, invocation

**Controller reservation**:
The short-lived atomic ownership claim used while one controller moves from
configuration to a durable recovery record.
_Avoid_: Lock, pending controller, startup marker

**Enabled**:
The requested condition in which the controller must remain running across
interruptions and restarts.
_Avoid_: Active, alive

**Recovery snapshot**:
The original settings captured for one controller session.
_Avoid_: State, backup, session state

**Recovery record**:
The durable ownership record for a controller session. It remains after an
interrupted controller exits so restoration can continue.
_Avoid_: Dirty marker, crash marker

**Recovery required**:
The lifecycle phase in which no controller is alive but a recovery record
remains.
_Avoid_: Dirty, unclean, failed

**Brightness pending**:
The condition in which power settings are restored but the built-in display is
unavailable, so its saved brightness still needs to be applied.
_Avoid_: Recovery required, deferred session
