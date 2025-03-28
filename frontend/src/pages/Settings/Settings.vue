<template>
    <NotificationTimer
        :showNotification="showNotification"
        :notificationTitle="notificationTitle"
        :notificationMessage="notificationMessage"
        :backgroundColor="backgroundColor"
        @dismissPopup="dismissPopup"
    />
    <div class="flex flex-col justify-center items-center h-screen">
        <div class="flex h-full w-full">
            <div :class="['ring-1 shadow-sm ring-black ring-opacity-5', isNavMinimized ? 'w-20' : 'w-60']">
                <Navbar @update:isMinimized="(value) => (isNavMinimized = value)" />
            </div>
            <div class="flex-1 bg-white ring-1 ring-black ring-opacity-5">
                <div class="flex flex-col h-full">
                    <main class="bg-gray-50 ring-1 ring-black ring-opacity-5">
                        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                            <div class="flex items-center">
                                <div class="w-full flex items-center justify-center py-6 2xl:py-7">
                                    <div class="sm:hidden"></div>
                                    <div class="hidden sm:block w-full">
                                        <nav class="flex justify-center space-x-4 w-full" aria-label="Tabs">
                                            <div
                                                class="text-sm font-medium cursor-pointer"
                                                :class="[
                                                    'flex space-x-2 items-center rounded-md py-2',
                                                    {
                                                        'bg-gray-500 bg-opacity-10 hover:text-gray-800 px-12':
                                                            activeSection === 'account',
                                                        'hover:bg-gray-500 hover:bg-opacity-10 hover:text-gray-800 px-8':
                                                            activeSection !== 'account',
                                                    },
                                                ]"
                                                @click="setActiveSection('account')"
                                            >
                                                <user-icon class="w-4 h-4" />
                                                <a
                                                    :class="{
                                                        'text-gray-800': activeSection === 'account',
                                                        'text-gray-600': activeSection !== 'account',
                                                    }"
                                                    class="text-sm font-medium"
                                                >
                                                    {{ $t("settingsPage.accountPage.myAccountTitle") }}
                                                </a>
                                            </div>
                                            <div
                                                class="text-sm font-medium cursor-pointer"
                                                :class="[
                                                    'flex space-x-2 items-center rounded-md py-2',
                                                    {
                                                        'bg-gray-500 bg-opacity-10 hover:text-gray-800 px-12':
                                                            activeSection === 'preferences',
                                                        'hover:bg-gray-500 hover:bg-opacity-10 hover:text-gray-800 px-8':
                                                            activeSection !== 'preferences',
                                                    },
                                                ]"
                                                @click="setActiveSection('preferences')"
                                            >
                                                <adjustments-vertical-icon class="w-4 h-4" />
                                                <a
                                                    :class="{
                                                        'text-gray-800': activeSection === 'preferences',
                                                        'text-gray-600': activeSection !== 'preferences',
                                                    }"
                                                >
                                                    {{ $t("settingsPage.preferencesPage.preferencesTitle") }}
                                                </a>
                                            </div>
                                        </nav>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </main>

                    <div class="overflow-y-auto custom-scrollbar">
                        <div v-if="activeSection === 'account'">
                            <MyAccountMenu />
                        </div>

                        <div v-if="activeSection === 'preferences'">
                            <PreferencesMenu />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, provide } from "vue";
import "@fortawesome/fontawesome-free/css/all.css";
import NotificationTimer from "@/global/components/NotificationTimer.vue";
import { AdjustmentsVerticalIcon, UserIcon } from "@heroicons/vue/24/outline";
import { displayErrorPopup, displaySuccessPopup } from "@/global/popUp";
import PreferencesMenu from "@/pages/Settings/components/PreferencesMenu.vue";
import MyAccountMenu from "@/pages/Settings/components/MyAccountMenu.vue";
import Navbar from "@/global/components/Navbar.vue";
import { i18n } from "@/global/preferences";
import { getData, postData } from "@/global/fetchData";
import { EmailLinked } from "@/global/types";
import { Plan } from "./utils/types";

const showNotification = ref(false);
const notificationTitle = ref("");
const notificationMessage = ref("");
const backgroundColor = ref("");
const timerId = ref<number | null>(null);

const userPlan = ref<Plan | null>(null);
const activeSection = ref("account");
const isAddUserDescriptionModalOpen = ref(false);
const isAccountDeletionModalOpen = ref(false);
const isUnlinkEmailModalOpen = ref(false);
const isUpdateUserDescriptionModalOpen = ref(false);
const isTroubleshootingMenuModalOpen = ref(false);
const isImapSmtpModalOpen = ref(false);
const isDeleteRadioButtonChecked = ref(false);
const emailSelected = ref("");
const userDescription = ref("");
const emailsLinked = ref<EmailLinked[]>([]);
const isNavMinimized = ref(localStorage.getItem("navbarMinimized") === "true");

provide("displayPopup", displayPopup);
provide("isImapSmtpModalOpen", isImapSmtpModalOpen);
provide("openAddUserDescriptionModal", openAddUserDescriptionModal);
provide("closeAddUserDescriptionModal", closeAddUserDescriptionModal);
provide("openAccountDeletionModal", openAccountDeletionModal);
provide("closeAccountDeletionModal", closeAccountDeletionModal);
provide("openUpdateUserDescriptionModal", openUpdateUserDescriptionModal);
provide("closeUpdateUserDescriptionModal", closeUpdateUserDescriptionModal);
provide("openTroubleshootingMenu", openTroubleshootingMenu);
provide("closeTroubleshootingMenu", closeTroubleshootingMenu);
provide("openUnLinkModal", openUnLinkModal);
provide("closeUnlinkEmailModal", closeUnlinkEmailModal);
provide("userDescription", userDescription);
provide("isDeleteRadioButtonChecked", isDeleteRadioButtonChecked);
provide("isUpdateUserDescriptionModalOpen", isUpdateUserDescriptionModalOpen);
provide("isTroubleshootingMenuModalOpen", isTroubleshootingMenuModalOpen);
provide("isAccountDeletionModalOpen", isAccountDeletionModalOpen);
provide("isAddUserDescriptionModalOpen", isAddUserDescriptionModalOpen);
provide("userPlan", userPlan);
provide("isUnlinkEmailModalOpen", isUnlinkEmailModalOpen);
provide("emailSelected", emailSelected);
provide("emailsLinked", emailsLinked);

onMounted(() => {
    document.addEventListener("keydown", handleKeyDown);
    getUserPlan();
});

async function getUserPlan() {
    const result = await getData("user/preferences/plan/");
    if (!result.success) {
        displayPopup("error", i18n.global.t("settingsPage.accountPage.failedToFetchPlan"), result.error as string);
    } else {
        userPlan.value = result.data;
    }
}

function closeUnlinkEmailModal() {
    isUnlinkEmailModalOpen.value = false;
}

function closeUpdateUserDescriptionModal() {
    isUpdateUserDescriptionModalOpen.value = false;
}

async function openUnLinkModal(email: string) {
    emailSelected.value = email;

    if (emailsLinked.value.length === 1) {
        displayPopup?.(
            "error",
            i18n.global.t("settingsPage.accountPage.unableToDeletePrimaryEmail"),
            i18n.global.t("settingsPage.accountPage.deleteAccountInstruction")
        );
        return;
    }
    isUnlinkEmailModalOpen.value = true;
}

async function openUpdateUserDescriptionModal(email: string) {
    emailSelected.value = email;

    const result = await postData(`user/social_api/get_user_description/`, { email: email });

    if (!result.success) {
        displayPopup?.(
            "error",
            i18n.global.t("settingsPage.accountPage.errorRetrievingUserDescription"),
            result.error as string
        );
        return;
    }

    isUpdateUserDescriptionModalOpen.value = true;
    userDescription.value = result.data.description;
}

function isAModalOpen() {
    return (
        isUpdateUserDescriptionModalOpen.value ||
        isAddUserDescriptionModalOpen.value ||
        isAccountDeletionModalOpen.value ||
        isUnlinkEmailModalOpen.value ||
        isImapSmtpModalOpen.value
    );
}

function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Tab" && !isAModalOpen()) {
        const usernameInput = document.getElementById("usernameInput") as HTMLInputElement | null;
        const confirmPassword = document.getElementById("confirmPassword") as HTMLInputElement | null;
        const newPassword = document.getElementById("newPassword") as HTMLInputElement | null;

        if (
            usernameInput?.isEqualNode(document.activeElement) ||
            confirmPassword?.isEqualNode(document.activeElement) ||
            newPassword?.isEqualNode(document.activeElement)
        ) {
            return;
        }

        event.preventDefault();
        switchActiveSection();
    }

    if (event.key === "Escape") {
        if (isUpdateUserDescriptionModalOpen.value) {
            closeUpdateUserDescriptionModal();
        } else if (isAddUserDescriptionModalOpen?.value) {
            closeAddUserDescriptionModal();
        } else if (isAccountDeletionModalOpen?.value) {
            closeAccountDeletionModal();
        } else if (isUnlinkEmailModalOpen.value) {
            closeUnlinkEmailModal();
        }
    }
}

function openAddUserDescriptionModal() {
    isAddUserDescriptionModalOpen.value = true;
}

function closeAddUserDescriptionModal() {
    isAddUserDescriptionModalOpen.value = false;
}

function closeAccountDeletionModal() {
    isAccountDeletionModalOpen.value = false;
}

function closeTroubleshootingMenu() {
    isTroubleshootingMenuModalOpen.value = false;
}

function openTroubleshootingMenu() {
    isTroubleshootingMenuModalOpen.value = true;
}

function openAccountDeletionModal() {
    if (isDeleteRadioButtonChecked?.value) {
        isAccountDeletionModalOpen.value = true;
    } else {
        displayPopup?.(
            "error",
            i18n.global.t("settingsPage.accountPage.confirmationRequired"),
            i18n.global.t("settingsPage.accountPage.checkBoxApprovalDeletion")
        );
    }
}

function switchActiveSection() {
    const nextSection: { [key: string]: string } = {
        account: "preferences",
        preferences: "account",
    };

    setActiveSection(nextSection[activeSection.value]);
}

function setActiveSection(section: string) {
    activeSection.value = section;
}

function displayPopup(type: "success" | "error", title: string, message: string) {
    if (type === "error") {
        displayErrorPopup(showNotification, notificationTitle, notificationMessage, backgroundColor, title, message);
    } else {
        displaySuccessPopup(showNotification, notificationTitle, notificationMessage, backgroundColor, title, message);
    }
    timerId.value = setTimeout(dismissPopup, 4000);
}

function dismissPopup() {
    showNotification.value = false;
    if (timerId.value !== null) {
        clearTimeout(timerId.value);
    }
}
</script>
