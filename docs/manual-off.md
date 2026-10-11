# Switched off by hand

Switching the light off in an occupied room — wall switch, app, voice
assistant, LLM agent or another automation — means **off**. The radar must
not switch it on again, least of all in the bedroom while somebody sleeps.

## What counts

A `light.turn_off` service call from anywhere else than the integration is
the evidence, also right after the light came on for entering. A lamp that
reports off without such a call counts as switched off by hand unless the
integration itself sent a command in the 10 s before (its own echo).

## How long it lasts

The light stays off:

- while you are in the room, also when you turn over in bed and the radar
  sees a "new" target;
- after leaving briefly — to the bathroom at night and back;
- when the household limit gives a sleeper's place to somebody seen
  elsewhere (this does not count as leaving).

It ends when:

- you switch the light on again: it is automatic again;
- with a *Home* entry, after the room was empty for 30 minutes (option
  *Switched off by hand ends after the room was empty for*) **and** somebody
  evidently left it (through a door, out of the home, released, hold off);
- somebody comes in through a door after nobody was seen in the room for
  that time;
- at once in the room somebody enters the home through (stairs, front door):
  the lights you switched off when leaving come on again when you return.

Setting the option to 0 keeps the old behaviour: only until the next
entering.

## Why occupancy is not released

Switching the light off does not clear the room. Otherwise the next movement
in bed would be a new entering and switch the light on again.

## Voice commands

With Home Assistant's built-in conversation agent a sentence like
"turn off the light in the bedroom" calls `light.turn_off` and is honoured
immediately. Custom sentence files must not override built-in rule names
(for example `{vor}` or `{aus}` in German): Home Assistant merges all custom
sentences into one namespace, a same-named expansion rule silently replaces
the other, and the sentence falls through to an LLM or matches the wrong
intent. Give your own rules a unique prefix.
