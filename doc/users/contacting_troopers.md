# Contacting troopers

This page can be found at: [g.co/bugatrooper](https://g.co/bugatrooper)

Have an issue with a piece of build infrastructure?
Our troopers are here to help.

Oncall hours: we cover working hours in the Pacific timezone:
+ 1600 - 0000 UTC (900 - 1700 MTV)

There is no designated oncall coverage for EMEA or APAC hours. Volunteers in
those regions may provide assistance on mailing lists for urgent issues, but
there's no guarantee.

If you are contacting a trooper to see if there is an issue with a service,
visit the [ChOps Status Dashboard](https://chopsdash.appspot.com) first.
If the "Current Status" of the service shows red/yellow, that means there is a known
disruption or outage, and the Trooper is already aware. No need to contact us further!

The primary way to contact a trooper is via [crbug.com](https://crbug.com) using
the templates and priorities established below. If you need to find the current
trooper, check [build.chromium.org](https://build.chromium.org), or
[vi/chrome_infra](http://vi/chrome_infra) (internal link). If crbug.com is down
and you are unable to file a bug, please contact the team on
[infra-dev@chromium.org](mailto:infra-dev@chromium.org).

Small or non-urgent questions can also be posted in the [#ops] Chromium slack
channel or the [chops-hangout channel] (internal).

If you know your issue is with the physical hardware, or otherwise should be
handled by the Systems team, please follow their
[Rules of Engagement](http://shortn/_x6Y10rxpKG) (internal).

## Bug Templates

For fastest response, please use the provided templates:

*   **[General requests]**: for most cases.
*   [Machine restart requests]: if a machine appears to be offline and you
    know that it's managed by the Labs team.
*   [Mobile device restart requests]: if a mobile device appears to be offline
    and you know that it's managed by the Labs team.

Also make sure to include the machine name (e.g. build11-m1)
as well as the builder name (Builder: win-archive-rel) when applicable.

## Priority Levels

Priorities are set using the `Pri=N` label. Use the following as your guideline:

*   Pri-0: Immediate attention desired.  The trooper will stop everything they are
    doing and investigate.
    *   Examples: CQ no longer committing changes.
*   Pri-1: Resolution desired within an hour or two.
    * Examples: disk full on device, device offline, sheriff-o-matic data stale.
*   Pri-2: Should be handled today.
*   Pri-3: Non-urgent. If the trooper cannot get to this today due to other
    incidents, it is ok to wait.
    *   Examples: Large change that will need trooper assistance, aka,
        "I'd like to land this gigantic change that may break the world"</span>

## Life of a Request

Status will be tracked using the Status field, with the 'owner' field unset.
The trooper queue relies on the 'owner' field being unset to track issues
properly, with troopers setting the owners field for particularly long-running
issues.  Please do not assign issues to the trooper directly, doing so may
actually increase the time taken to respond to an issue. Behind the scenes, our
Troopers will review and triage the bug, as-needed, to corresponding Chrome
Operations teams to be addressed.

All requests should contain the “Infra-Troopers” label such that we can properly
triage the request and to indicate that this is user-filed.

*   Untriaged: Your issue will show up in the queue to the trooper as untriaged.
    Once they acknowledge the bug, the status will change.
*   Available: Trooper has ack'ed, if not Pri-0, this means they have not started working on it.
*   Assigned:
    *   Trooper has triaged and determined there is a suitable owner and
        appropriately assigned.
    *   If that owner is YOU this indicates that they need more information from you
        in order to proceed.  Please provide the information, and then unset
        'owner' so the issue shows up in the queue again.
*   Started: Your issue is being handled, either by the Trooper or other owner.
*   Fixed: The trooper believes the issue is resolved and no further action is required on their part.

## Service Hours

Troopers provide full time coverage with the expected response times outlined
above during the Pacific work day. Other times support is provided best-effort.

## More Information

View the [current trooper queue].

Other available team trooper queues within Chrome Operations.

* [DevX trooper queue]
* [Foundation trooper queue]

Common Non-Trooper Requests:

*   [Contact a Git Admin](https://bugs.chromium.org/p/chromium/issues/entry?template=Infra-Git)
*   [File Chrome OS infra bug](https://bugs.chromium.org/p/chromium/issues/entry?template=Defect%20report%20from%20developer&components=Infra>ChromeOS&labels=Restrict-View-Google&summary=%5BBrief%20description%20of%20problem%5D)
*   [Check the Chrome OS on-call channel](http://go/crosoncall) (internal)

[#ops]: https://chromium.slack.com/messages/CGM8DQ3ST/
[chops-hangout channel]: http://go/chops-hangout
[Machine restart requests]: http://go/chrome-labs-fixit-bug
[Mobile device restart requests]: http://go/chrome-labs-fixit-bug
[General requests]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers&summary=%5BBrief%20description%20of%20problem%5D&comment=Please%20provide%20the%20details%20for%20your%20request%20here.%0A%0ASet%20Pri-0%20iff%20it%20requires%20immediate%20attention,%20Pri-1%20if%20resolution%20within%20a%20few%20hours%20is%20acceptable,%20and%20Pri-2%20if%20it%20just%20needs%20to%20be%20handled%20today.
[current trooper queue]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=Infra%3DTroopers+-has%3Aowner+OR+owner%3Ame+Infra%3DTroopers+OR+Infra%3DTroopers+Pri%3D0&sort=-modified&groupby=pri&colspec=ID+Component+Status+Owner+Summary+Blocking+BlockedOn+Opened+Modified&x=m&y=releaseblock&cells=ids
[DevX trooper queue]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=DevX%3DTroopers+-has%3Aowner+OR+owner%3Ame+DevX%3DTroopers+OR+DevX%3DTroopers+Pri%3D0&sort=-modified&groupby=pri&colspec=ID+Component+Status+Owner+Summary+Blocking+BlockedOn+Opened+Modified&x=m&y=releaseblock&cells=ids
[Foundation trooper queue]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=Foundation%3DTroopers+-has%3Aowner+OR+owner%3Ame+Foundation%3DTroopers+OR+Foundation%3DTroopers+Pri%3D0&sort=-modified&groupby=pri&colspec=ID+Component+Status+Owner+Summary+Blocking+BlockedOn+Opened+Modified&x=m&y=releaseblock&cells=ids
[go/bug-a-trooper]: http://go/bug-a-trooper
