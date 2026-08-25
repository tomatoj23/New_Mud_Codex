# New_Mud

New_Mud is a Chinese wuxia MUD that rebuilds selected XKX100 experiences on a self-developed, web-first engine. This glossary records project-specific language without defining implementation or delivery requirements.

## Language

**User**:
The platform login and administrative authorization subject. A User is not a game-world Character and does not itself represent a Presence.
_Avoid_: player character, GameAccount, AuthSession

**GameAccount**:
The per-instance game identity permanently associated with one User. It owns CharacterOwnership and player-domain relationships but does not carry PlatformRole permissions.
_Avoid_: User, login session, character slot

**Character**:
A persistent playable game persona controlled through CharacterOwnership. The first release allows at most one Character per GameAccount while retaining the ownership relation for future expansion.
_Avoid_: User, Actor, Presence

**CharacterOwnership**:
The explicit relationship by which a GameAccount owns and may control a Character. It is separate from the User-to-GameAccount identity mapping.
_Avoid_: account membership, Presence

**Entity**:
A world object with a stable identity and lifecycle, including Character, NPC, Room, Exit and Item. An Entity may be persistent without being controllable by a player.
_Avoid_: database row, Actor

**Actor**:
An Entity that can participate as the subject or target of a world action. In the first release this includes Character and NPC; Room, Exit, Item and platform operators are not Actors merely because they are addressable objects.
_Avoid_: User, Entity, GM

**NPC**:
A non-player Actor controlled by world rules or server-owned behavior rather than a User's CharacterOwnership.
_Avoid_: Character, system operator

**Room**:
A world Entity representing a location in the room-and-exit topology. A Room can contain Actors and Items but is not itself an Actor.
_Avoid_: scene snapshot, region

**Item**:
A world Entity representing a carried, equipped, contained or dropped game object. An Item can be an action target but is not an Actor.
_Avoid_: LootClaim, inventory row

**AuthSession**:
The authenticated session lifecycle created by login for one User. It is distinct from a physical ConnectionSession and may exist without an active Presence.
_Avoid_: WebSocket connection, access token

**Presence**:
A temporary control lease binding an AuthSession to a Character. It is not the Character's identity and can move through active, grace_disconnected, taken_over and closed states.
_Avoid_: AuthSession, resume ticket, online flag

**GameAccountLifecycle**:
The account-control lifecycle `active -> cooling_off -> retired`. A cooling-off account can be reopened only with a valid RecoveryCode; a retired account cannot be restored, while stable identifiers and required history remain auditable.
_Avoid_: AuthSession state, temporary ban, deleted account

**CharacterCreationProfile**:
A versioned definition of the choices and starting state available when a Character is first created.
_Avoid_: character template, birth config, starter preset

**CharacterDisplayName**:
The public, instance-unique name by which a Character is identified to players, distinct from an account name and the Character's stable identity.
_Avoid_: username, account name, character ID

**Sparring**:
A mutually accepted, non-lethal fight between Characters that cannot become involuntary or lethal player combat.
_Avoid_: PvP, duel, player kill

**SafeDefeat**:
The non-permanent outcome applied to a defeated Character, preserving items and irreversible progress while returning the Character to a safe playable state.
_Avoid_: death, resurrection, permadeath

**RecoveryCode**:
A player-held proof used to recover access when a password is lost; it is not a login credential, AuthSession, or gameplay identity.
_Avoid_: recovery token, backup password, refresh token

**RetiredCharacter**:
A Character that can no longer be controlled after its GameAccount is closed, while its stable identity and historical relationships remain meaningful.
_Avoid_: deleted character, banned character, dead character

**GoldenSkillChain**:
A deterministic, source-bound sequence used to verify one complete martial-arts behavior path against the frozen XKX100 baseline.
_Avoid_: combat smoke test, sample skill, synthetic fixture

**PlayerBlock**:
A player's private boundary against another Actor, preventing direct contact and suppressing that Actor's ordinary public messages without changing what other players receive.
_Avoid_: channel mute, GM mute, ban

**ChannelMute**:
A player's choice not to receive a ChatChannel, without restricting anyone else's ability to speak or receive it.
_Avoid_: player block, GM mute, channel ban

**ModerationCase**:
The auditable record that joins a player report, immutable message evidence, review decisions, sanctions, and any appeal.
_Avoid_: report message, support ticket, chat log

**PresenceRecovery**:
The same-AuthSession recovery of its own active or grace Presence after the in-memory resume credential is lost; it is never cross-session takeover.
_Avoid_: session resume, takeover, re-enter

**VillageTopologyEnvelope**:
The source-bound scope that fixes the Village's Rooms, Exits, boundaries, and static Entity identities without claiming that every interaction is behaviorally aligned.
_Avoid_: village compatibility, full village alignment, village import

**VillageInteractionEnvelope**:
The capability-by-capability scope of Village behaviors that have source-bound evidence and may be claimed as verified.
_Avoid_: village topology, implemented NPCs, supported commands

**LootClaim**:
A temporary, authoritative right to pick up a dropped Item before it becomes publicly available; it is not permanent Item ownership.
_Avoid_: item owner, instanced loot, inventory binding

**PublicV1Gate**:
The release gate that determines whether a completed M1 build may accept real public players; it is independent of the numbered requirement milestones.
_Avoid_: M1-B, public beta, release candidate

**UnavailableInteraction**:
A source-known behavior outside the active interaction envelope that must resolve explicitly as unavailable instead of being approximated or claimed as aligned.
_Avoid_: unknown command, stub behavior, partial support

**ItemRetirement**:
The end of an Item's active world lifecycle while preserving the identity and history needed by authoritative records.
_Avoid_: item deletion, despawn, database cleanup

**SourceSnapshot**:
An immutable, content-addressed description of the exact XKX100 source bytes and inclusion rules used as evidence for a conversion or compatibility claim.
_Avoid_: source folder, local checkout, latest source

**ReleaseManifest**:
The immutable record that identifies the code, requirements, contracts, migrations, active content batch, source snapshot, compatibility envelopes, and test evidence that are released together.
_Avoid_: deployment note, build metadata, version string

**PublicV1**:
The first publicly operated product version that has passed `PublicV1Gate`; it is distinct from the internal M1 delivery and from a general claim of XKX100 parity.
_Avoid_: M1, public beta, full release
