<template>
    <ScheduleSendModal :isOpen="isScheduleSendModalOpen" @closeModal="closeScheduleSendModal" />
    <div class="inline-flex rounded-lg shadow-lg items-stretch">
        <button
            @click="sendEmail"
            :class="[
                emailsLinked.filter(
                    (emailLinked) =>
                        emailLinked.email === emailSelected &&
                        !emailLinked.isServerConfig &&
                        emailLinked.typeApi === MICROSOFT
                ).length === 1
                    ? 'rounded-l-lg'
                    : 'rounded-lg',
                'bg-gray-700 px-6 py-2 text-md font-semibold text-white hover:bg-gray-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-600 flex gap-x-2 items-center 2xl:px-7 2xl:py-3 2xl:text-lg',
            ]"
        >
            {{ $t("constants.userActions.send") }}
            <PaperAirplaneIcon class="w-4 2xl:w-5" aria-hidden="true" />
        </button>
        <Menu
            v-if="
                emailsLinked.filter(
                    (emailLinked) =>
                        emailLinked.email === emailSelected &&
                        !emailLinked.isServerConfig &&
                        emailLinked.typeApi === MICROSOFT
                ).length === 1
            "
            as="div"
            class="relative -ml-px block items-stretch"
        >
            <MenuButton
                @click="toggleMenu"
                class="relative inline-flex items-center rounded-r-lg px-2 py-2 text-white border-l border-gray-300 bg-gray-700 hover:bg-gray-900 focus:z-10 2xl:px-3 2xl:py-3"
            >
                <ChevronDownIcon class="h-8 w-5 2xl:h-9 2xl:w-6" aria-hidden="true" />
            </MenuButton>
            <transition
                enter-active-class="transition ease-out duration-100"
                enter-from-class="transform opacity-0 -translate-y-2"
                enter-to-class="transform opacity-100 translate-y-0"
                leave-active-class="transition ease-in duration-75"
                leave-from-class="transform opacity-100 translate-y-0"
                leave-to-class="transform opacity-0 -translate-y-2"
            >
                <MenuItems
                    v-if="isMenuOpen"
                    class="absolute right-0 z-10 -mr-1 bottom-full mb-2 w-56 origin-bottom-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
                >
                    <div class="py-1">
                        <button
                            type="button"
                            :class="[active ? 'bg-gray-100 text-gray-900' : 'text-gray-700', 'block px-4 py-2 text-sm']"
                            @click="openScheduleSendModal"
                        >
                            {{ $t("constants.sendEmailConstants.sendScheduledEmail") }}
                        </button>
                    </div>
                </MenuItems>
            </transition>
        </Menu>
    </div>
</template>

<script setup lang="ts">
import { MICROSOFT } from "@/global/const";
import { postData } from "@/global/fetchData";
import { i18n } from "@/global/preferences";
import { EmailLinked, Recipient, UploadedFile } from "@/global/types";
import Quill from "quill";
import { ChevronDownIcon, PaperAirplaneIcon } from "@heroicons/vue/24/outline";
import { inject, onMounted, onUnmounted, Ref, ref } from "vue";
import ScheduleSendModal from "./ScheduleSendModal.vue";
import { Menu, MenuButton, MenuItems } from "@headlessui/vue";

const isMenuOpen = ref(false);
const active = ref(false);
const isScheduleSendModalOpen = ref(false);
const subjectInput = inject<Ref<string>>("subjectInput") || ref("");
const selectedPeople = inject<Ref<Recipient[]>>("selectedPeople") || ref([]);
const fileObjects = inject<Ref<File[]>>("fileObjects") || ref([]);
const selectedCC = inject<Ref<Recipient[]>>("selectedCC") || ref([]);
const selectedBCC = inject<Ref<Recipient[]>>("selectedBCC") || ref([]);
const stepContainer = inject<Ref<number>>("stepContainer") || ref(0);
const emailSelected = inject<Ref<string>>("emailSelected") || ref("");
const AIContainer =
    inject<Ref<HTMLElement | null>>("AIContainer") || ref<HTMLElement | null>(document.getElementById("AIContainer"));
const uploadedFiles = inject<Ref<UploadedFile[]>>("uploadedFiles") || ref([]);
const displayPopup = inject<(type: "success" | "error", title: string, message: string) => void>("displayPopup");
const displayMessage = inject<(message: string, aiIcon: string) => void>("displayMessage");
const emailsLinked = inject<Ref<EmailLinked[]>>("emailsLinked", ref([]));

const getQuill = inject<() => Quill | null>("getQuill");

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.ctrlKey && event.key === "Enter") {
        sendEmail();
    }
};

onMounted(() => {
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
    document.removeEventListener("click", handleClickOutside);
    document.removeEventListener("keydown", handleKeyDown);
});

const toggleMenu = () => {
    isMenuOpen.value = !isMenuOpen.value;
};

const closeScheduleSendModal = () => {
    isScheduleSendModalOpen.value = false;
};

const handleClickOutside = (event: MouseEvent) => {
    const target = event.target as Element;
    if (!target.closest(".relative")) {
        isMenuOpen.value = false;
    }
};

async function sendEmail() {
    const quillInstance = getQuill?.();
    if (!AIContainer.value || !quillInstance) return;

    const emailSubject = subjectInput.value;
    const emailBody = quillInstance.root.innerHTML;

    if (!emailSubject.trim()) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoSubject")
        );
        return;
    }

    if (emailBody === "<p><br></p>") {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoObject")
        );
        return;
    }

    if (selectedPeople.value.length === 0) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoRecipient")
        );
        return;
    }

    const formData = new FormData();

    const formattedBody = emailBody
        .replace(/<p>/g, "")
        .replace(/<\/p>/g, "<br>")
        .replace(/<br><br>/g, "<br>")
        .replace(/<br>$/, "");

    formData.append("subject", emailSubject);
    formData.append("message", formattedBody);

    fileObjects.value.forEach((file) => formData.append("attachments", file));

    selectedPeople.value.forEach((person) => formData.append("to", person.email));

    if (selectedCC.value.length > 0) {
        selectedCC.value.forEach((person) => formData.append("cc", person.email));
    }

    if (selectedBCC.value.length > 0) {
        selectedBCC.value.forEach((person) => formData.append("bcc", person.email));
    }

    formData.append("email", emailSelected.value);

    try {
        const result = await postData("user/social_api/send_email/", formData, true);

        if (!result.success) {
            displayPopup?.(
                "error",
                i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
                result.error || i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorGeneral")
            );
            return;
        }

        displayPopup?.(
            "success",
            i18n.global.t("constants.popUpConstants.successMessages.success"),
            i18n.global.t("constants.popUpConstants.successMessages.emailSuccessfullySent")
        );

        subjectInput.value = "";
        quillInstance.root.innerHTML = "";
        selectedPeople.value = [];
        selectedCC.value = [];
        selectedBCC.value = [];
        stepContainer.value = 0;
        AIContainer.value.innerHTML = "";
        localStorage.removeItem("uploadedFiles");
        uploadedFiles.value = [];
        fileObjects.value = [];

        const ai_icon = `<path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />`;
        displayMessage?.(i18n.global.t("constants.sendEmailConstants.emailRecipientRequest"), ai_icon);
    } catch (error) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorGeneral")
        );
    }
}

function validateScheduledSend(): boolean {
    const quillInstance = getQuill?.();
    if (!quillInstance) return false;

    for (const tupleEmail of emailsLinked.value) {
        if (emailSelected.value === tupleEmail.email && tupleEmail.typeApi !== MICROSOFT) {
            displayPopup?.(
                "error",
                "Email service provider not supported",
                "Scheduled send is only available for Outlook accounts"
            );
            return false;
        }
    }
    if (!subjectInput.value.trim()) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoSubject")
        );
        return false;
    } else if (quillInstance.root.innerHTML == "<p><br></p>") {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoObject")
        );
        return false;
    } else if (selectedPeople.value.length === 0) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendErrorNoRecipient")
        );
        return false;
    }
    return true;
}

async function openScheduleSendModal() {
    if (!validateScheduledSend()) return;

    isScheduleSendModalOpen.value = true;
}
</script>
