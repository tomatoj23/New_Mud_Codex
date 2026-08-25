# New_Mud

New_Mud is a Chinese wuxia MUD that rebuilds selected XKX100 experiences on a self-developed, web-first engine. This glossary records project-specific language without defining implementation or delivery requirements.

## Language

### Identity and ownership

**User**:
The platform login and administrative authorization subject. A User is not a game-world Character and does not itself represent a Presence.
_Avoid_: player character, GameAccount, AuthSession

**AuthIdentity**:
An external authentication identity associated with a User. It identifies an authentication source without owning game-world relationships.
_Avoid_: login source, credential record, GameAccount

**GameAccount**:
The per-instance game identity permanently associated with one User. It owns CharacterOwnership and player-domain relationships but does not carry PlatformRole permissions.
_Avoid_: User, login session, character slot

**PlatformRole**:
An administrative authorization role held by a User. It does not express Character ownership, player status, or world capabilities.
_Avoid_: game permission, Character role, GameAccount permission

**Character**:
A persistent playable game persona controlled through CharacterOwnership. The first release allows at most one Character per GameAccount while retaining the ownership relation for future expansion.
_Avoid_: User, Actor, Presence

**CharacterOwnership**:
The explicit relationship by which a GameAccount owns and may control a Character. It is separate from the User-to-GameAccount identity mapping.
_Avoid_: account membership, Presence

### World and content

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

**Exit**:
A directed world Entity connecting one Room to another within the world topology.
_Avoid_: portal implementation, generic link, Region

**Region**:
A named grouping used to organize Rooms and world content. It is not itself a location occupied by an Actor.
_Avoid_: Room, scene, zone server

**Blueprint**:
The stable content identity whose revisions describe how a kind of world or gameplay content is defined.
_Avoid_: Prototype, mutable template row, Entity

**BlueprintRevision**:
An immutable version of a Blueprint definition, with an explicit draft or published lifecycle position.
_Avoid_: mutable Blueprint, runtime Entity, latest template

**ContentReleaseBatch**:
An immutable set of published BlueprintRevisions selected to become active together as one content release decision.
_Avoid_: partial release diff, latest drafts, deployment

**MUDLib**:
The runtime content package selected for a New_Mud instance. Historical LPC source is conversion input, not a runtime MUDLib.
_Avoid_: Source LPC MUDLib, plugin pack, source tree

### Sessions and character lifecycle

**ConnectionSession**:
A single live client transport connection. It is distinct from authenticated identity and from control of a Character.
_Avoid_: AuthSession, Presence, socket user

**AuthSession**:
The authenticated session lifecycle created by login for one User. It is distinct from a physical ConnectionSession and may exist without an active Presence.
_Avoid_: WebSocket connection, access token

**Presence**:
A temporary control lease binding an AuthSession to a Character. It is not the Character's identity and can move through active, grace_disconnected, taken_over and closed states.
_Avoid_: AuthSession, resume ticket, online flag

**PresenceSnapshot**:
A short-lived recovery checkpoint associated with a Presence lease. It is neither a Character identity nor a Presence itself.
_Avoid_: persisted Presence, Character save, session archive

**GameAccountLifecycle**:
The account-control lifecycle `active -> cooling_off -> retired`. A cooling-off account can be reopened only with a valid RecoveryCode; a retired account cannot be restored, while stable identifiers and required history remain auditable.
_Avoid_: AuthSession state, temporary ban, deleted account

**CharacterCreationProfile**:
A versioned definition of the choices and starting state available when a Character is first created.
_Avoid_: character template, birth config, starter preset

**CharacterDisplayName**:
The public, instance-unique name by which a Character is identified to players, distinct from an account name and the Character's stable identity.
_Avoid_: username, account name, character ID

**RecoveryCode**:
A player-held proof used to recover access when a password is lost; it is not a login credential, AuthSession, or gameplay identity.
_Avoid_: recovery token, backup password, refresh token

**RetiredCharacter**:
A Character that can no longer be controlled after its GameAccount is closed, while its stable identity and historical relationships remain meaningful.
_Avoid_: deleted character, banned character, dead character

**PresenceRecovery**:
The same-AuthSession recovery of its own active or grace Presence after the in-memory resume credential is lost; it is never cross-session takeover.
_Avoid_: session resume, takeover, re-enter

### Gameplay and evidence

**Sparring**:
A mutually accepted, non-lethal fight between Characters that cannot become involuntary or lethal player combat.
_Avoid_: PvP, duel, player kill

**SafeDefeat**:
The non-permanent outcome applied to a defeated Character, preserving items and irreversible progress while returning the Character to a safe playable state.
_Avoid_: death, resurrection, permadeath

**GoldenSkillChain**:
A deterministic, source-bound sequence used to verify one complete martial-arts behavior path against the frozen XKX100 baseline.
_Avoid_: combat smoke test, sample skill, synthetic fixture

### Community and communication

**PlayerBlock**:
A player's private boundary against another Actor, preventing direct contact and suppressing that Actor's ordinary public messages without changing what other players receive.
_Avoid_: channel mute, GM mute, ban

**ChannelMute**:
A player's choice not to receive a ChatChannel, without restricting anyone else's ability to speak or receive it.
_Avoid_: player block, GM mute, channel ban

**ModerationCase**:
The auditable record that joins a player report, immutable message evidence, review decisions, sanctions, and any appeal.
_Avoid_: report message, support ticket, chat log

**ChatChannel**:
A named shared conversation space with explicit participation and delivery boundaries.
_Avoid_: room broadcast, DirectMessage, generic channel

**DirectMessage**:
A private message sent from one Actor to another outside a ChatChannel.
_Avoid_: whisper command, ChatChannel, support ticket

**SystemNotice**:
A server-authored message for operational, safety, or game-wide communication rather than player speech.
_Avoid_: ChatMessage, GM impersonation, public chat

### World compatibility and active lifecycles

**VillageTopologyEnvelope**:
The source-bound scope that fixes the Village's Rooms, Exits, boundaries, and static Entity identities without claiming that every interaction is behaviorally aligned.
_Avoid_: village compatibility, full village alignment, village import

**VillageInteractionEnvelope**:
The capability-by-capability scope of Village behaviors that have source-bound evidence and may be claimed as verified.
_Avoid_: village topology, implemented NPCs, supported commands

**LootClaim**:
A temporary, authoritative right to pick up a dropped Item before it becomes publicly available; it is not permanent Item ownership.
_Avoid_: item owner, instanced loot, inventory binding

**UnavailableInteraction**:
A source-known behavior outside the active interaction envelope that must resolve explicitly as unavailable instead of being approximated or claimed as aligned.
_Avoid_: unknown command, stub behavior, partial support

**ItemRetirement**:
The end of an Item's active world lifecycle while preserving the identity and history needed by authoritative records.
_Avoid_: item deletion, despawn, database cleanup

**EffectTypeDefinition**:
The named and versioned meaning of a kind of ongoing effect. It defines the category a ConditionDefinition may express, not a particular effect on an Entity.
_Avoid_: EffectInstance, condition row, handler class

**ConditionDefinition**:
A versioned content definition of a condition tied to one EffectTypeDefinition.
_Avoid_: EffectInstance, runtime status, arbitrary payload

**EffectInstance**:
A concrete occurrence of a ConditionDefinition affecting a particular target over its lifecycle.
_Avoid_: ConditionDefinition, buff template, effect type

### Source and public release

**SourceSnapshot**:
An immutable, content-addressed description of the exact XKX100 source bytes and inclusion rules used as evidence for a conversion or compatibility claim.
_Avoid_: source folder, local checkout, latest source

**CompatibilityEnvelope**:
The source-bound scope within which a specific XKX100 compatibility claim is supported by explicit evidence.
_Avoid_: full compatibility, tested sample, general parity

**ReleaseManifest**:
The immutable record that identifies the code, requirements, contracts, migrations, active content batch, source snapshot, compatibility envelopes, and test evidence that are released together.
_Avoid_: deployment note, build metadata, version string

**CapacityProfile**:
A versioned statement of the reference environment, load, latency, stability, and recovery targets used for release evidence.
_Avoid_: load script, deployment size, informal performance target

**PublicV1Gate**:
The release gate that determines whether a completed M1 build may accept real public players; it is independent of the numbered requirement milestones.
_Avoid_: M1-B, public beta, release candidate

**PublicV1**:
The first publicly operated product version that has passed `PublicV1Gate`; it is distinct from the internal M1 delivery and from a general claim of XKX100 parity.
_Avoid_: M1, public beta, full release
