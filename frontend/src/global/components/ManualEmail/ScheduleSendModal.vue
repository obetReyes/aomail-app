<template>
    <transition name="modal-fade">
        <div
            @click.self="closeModal"
            class="fixed z-50 top-0 left-0 w-full h-full bg-black bg-opacity-50 flex items-center justify-center"
            v-if="isOpen"
        >
            <div class="bg-white rounded-lg relative w-[450px]">
                <div class="absolute right-0 top-0 hidden pr-4 pt-4 sm:block p-8">
                    <button
                        @click="closeModal"
                        type="button"
                        class="rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                    >
                        <XMarkIcon class="h-6 w-6" aria-hidden="true" />
                    </button>
                </div>
                <div class="flex items-center w-full h-16 bg-gray-50 ring-1 ring-black ring-opacity-5 rounded-t-lg">
                    <div class="ml-8 flex items-center space-x-1">
                        <p class="block font-semibold leading-6 text-gray-900">
                            {{ $t("constants.sendEmailConstants.pickSendingDateTime") }}
                        </p>
                    </div>
                </div>
                <div class="flex flex-col gap-4 px-8 py-6">
                    <div v-if="errorMessage" class="text-red-600 text-sm mb-4">
                        {{ errorMessage }}
                    </div>
                    <div class="flex flex-col sm:flex-row gap-4">
                        <div class="w-full">
                            <Datepicker v-model="selectedDate" />
                        </div>
                    </div>
                    <div class="mt-2 sm:mt-2 sm:flex sm:flex-row">
                        <button
                            type="button"
                            class="ml-auto rounded-md bg-gray-800 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                            @click="scheduleSend"
                        >
                            {{ $t("constants.sendEmailConstants.sendScheduledEmail") }}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </transition>
</template>

<script setup lang="ts">
import { inject, ref, onMounted, onUnmounted, Ref } from "vue";
import Quill from "quill";
import { Recipient, UploadedFile } from "@/global/types";
import { postData } from "@/global/fetchData";
import { i18n } from "@/global/preferences";
import Datepicker from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import { XMarkIcon } from "@heroicons/vue/24/outline";

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
const getQuill = inject<() => Quill | null>("getQuill");

const props = defineProps<{
    isOpen: boolean;
}>();

const emit = defineEmits<{
    (e: "closeModal"): void;
}>();

const closeModal = () => {
    emit("closeModal");
};

const selectedDate = ref<Date | undefined>(undefined);
const errorMessage = ref<string | null>(null);

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Enter" && props.isOpen) {
        scheduleSend();
    }
};

onMounted(() => {
    document.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
    document.removeEventListener("keydown", handleKeyDown);
});

async function scheduleSend() {
    const quillInstance = getQuill?.();
    if (!AIContainer.value || !quillInstance) return;

    if (!selectedDate.value) {
        errorMessage.value = i18n.global.t("constants.sendEmailConstants.selectTimeAndDate");
        return;
    }
    errorMessage.value = null;

    const result = await postData(`user/social_api/send_schedule_email/`, {
        subject: subjectInput.value,
        message: quillInstance.root.innerHTML,
        attachments: fileObjects.value,
        to: selectedPeople.value.map((person) => person.email),
        cc: selectedCC.value.map((person) => person.email),
        bcc: selectedBCC.value.map((person) => person.email),
        email: emailSelected.value,
        datetime: selectedDate.value.toISOString(),
    });

    if (!result.success) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.emailSendError"),
            result.error as string
        );
    } else {
        displayPopup?.(
            "success",
            i18n.global.t("constants.popUpConstants.successMessages.success"),
            i18n.global.t("constants.popUpConstants.successMessages.emailScheduledSuccessfully")
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

        const message = i18n.global.t("constants.sendEmailConstants.emailRecipientRequest");
        const aiIcon = `<path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />`;
        displayMessage?.(message, aiIcon);
    }
    closeModal();
}

/*
function validateScheduledSend(): boolean {
    if (!quill) return false;
    // ... validation logic
}
*/
</script>
