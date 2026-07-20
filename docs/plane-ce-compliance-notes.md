# Plane CE Compliance Notes

This is an engineering checklist, not legal advice.

## License Source

The local Plane checkout includes:

- `plane/LICENSE.txt`: GNU Affero General Public License v3.
- `plane/COPYRIGHT.txt`: Plane Software copyright notice and `SPDX-License-Identifier: AGPL-3.0-only`.
- Source file headers that reference Plane Software, AGPL-3.0-only, and the license file.

Public references:

- Plane repository license: https://github.com/makeplane/plane/blob/preview/LICENSE.txt
- Plane repository copyright notice: https://github.com/makeplane/plane/blob/preview/COPYRIGHT.txt
- AGPL v3 text: https://www.gnu.org/licenses/agpl-3.0.html

## Must Keep

- Keep `LICENSE.txt` and `COPYRIGHT.txt`.
- Keep existing copyright headers and SPDX identifiers.
- Keep third-party license/notice files where present.
- Keep a visible way for network users to obtain corresponding source for modified AGPL code.
- Mark local modifications clearly in project docs or release notes.
- Do not remove no-warranty and AGPL terms from redistributed artifacts.

## Must Not Do

- Do not remove Plane Software copyright notices.
- Do not hide or replace the AGPL license.
- Do not represent the modified CE build as a closed-source commercial Plane edition.
- Do not remove source-availability obligations when serving a modified build over a network.

## Commercial Entry Point Policy

AgentPM hides paid/commercial entry points from the CE UI but does not remove CE functionality.

Hidden or disabled entry points:

- Billing and Plans workspace settings navigation.
- Direct Billing page content.
- Upgrade badges and paid-plan prompts.
- Issue embed upgrade card.
- Commercial checkout/Stripe redirect CTAs.

Preserved CE functionality:

- Projects, work items, Pages, cycles, modules, views, intake, labels, states, members, API tokens, and AgentPM MCP extensions.
- License, copyright, source headers, and AGPL notices.

