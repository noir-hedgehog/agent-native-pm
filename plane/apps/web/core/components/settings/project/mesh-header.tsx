/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { PROJECT_SETTINGS } from "@plane/constants";
import type { TProjectSettingsTabs } from "@plane/types";
import { Breadcrumbs } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SettingsPageHeader } from "@/components/settings/page-header";
import { PROJECT_SETTINGS_ICONS } from "@/components/settings/project/sidebar/item-icon";

export const MeshProjectSettingsHeader = observer(function MeshProjectSettingsHeader({
  itemKey,
}: {
  itemKey: TProjectSettingsTabs;
}) {
  const settingsDetails = PROJECT_SETTINGS[itemKey];
  const Icon = PROJECT_SETTINGS_ICONS[itemKey];
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={settingsDetails.i18n_label}
                icon={<Icon className="size-4 text-tertiary" />}
              />
            }
          />
        </Breadcrumbs>
      }
    />
  );
});
