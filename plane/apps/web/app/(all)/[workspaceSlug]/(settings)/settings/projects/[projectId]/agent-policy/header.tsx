/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { PROJECT_SETTINGS } from "@plane/constants";
import { Breadcrumbs } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SettingsPageHeader } from "@/components/settings/page-header";
import { PROJECT_SETTINGS_ICONS } from "@/components/settings/project/sidebar/item-icon";

export const AgentPolicyProjectSettingsHeader = observer(function AgentPolicyProjectSettingsHeader() {
  const settingsDetails = PROJECT_SETTINGS.agent_policy;
  const Icon = PROJECT_SETTINGS_ICONS.agent_policy;

  return (
    <SettingsPageHeader
      leftItem={
        <div className="flex items-center gap-2">
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink label={settingsDetails.i18n_label} icon={<Icon className="size-4 text-tertiary" />} />
              }
            />
          </Breadcrumbs>
        </div>
      }
    />
  );
});
