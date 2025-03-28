<template>
    <div class="flex items-stretch gap-1 2xl:gap-2">
        <div class="flex-grow">
            <div class="relative items-stretch">
                <div class="relative w-full">
                    <div
                        v-if="!isFocus && !query"
                        class="absolute top-0 left-0 flex space-x-1 items-center pointer-events-none opacity-50 transition-opacity duration-200 h-full z-10"
                    >
                        <UserGroupIcon class="w-4 h-4 pointer-events-none 2xl:w-5 2xl:h-5" />
                        <label
                            for="recipients"
                            class="block text-sm font-medium leading-6 text-gray-900 pointer-events-none 2xl:text-base"
                        >
                            {{ $t("constants.recipient") }}
                        </label>
                    </div>
                    <Combobox as="div" v-model="selectedPerson" @update:model-value="personSelected">
                        <ComboboxInput
                            id="recipients"
                            :value="query"
                            @input="query = $event.target.value"
                            class="w-full h-10 2xl:h-11 border-0 bg-transparent py-2 text-gray-900 focus:ring-0 sm:text-sm sm:leading-6 2xl:py-3 2xl:text-base border-b border-gray-200 focus:border-gray-400 transition-colors duration-200"
                            :display-value="(person: any) => person?.name || ''"
                            @focus="handleFocus"
                            @blur="handleBlur"
                            @keydown.enter="handleEnterKey"
                        />
                        <ComboboxButton
                            class="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none 2xl:px-3"
                        >
                            <ChevronUpDownIcon class="h-5 w-5 text-gray-400 2xl:h-6 2xl:w-6" aria-hidden="true" />
                        </ComboboxButton>
                        <ComboboxOptions
                            v-if="filteredPeople.length > 0"
                            class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm 2xl:text-base"
                            style="z-index: 21"
                        >
                            <ComboboxOption
                                v-for="person in filteredPeople"
                                :key="person.email"
                                :value="person"
                                as="template"
                                v-slot="{ active, selected }"
                            >
                                <li
                                    :class="[
                                        'relative cursor-default select-none py-2 pl-3 pr-9',
                                        active ? 'bg-gray-800 text-white' : 'text-gray-900',
                                    ]"
                                >
                                    <div class="flex">
                                        <span :class="['truncate', selected && 'font-semibold']">
                                            {{ person.username }}
                                        </span>
                                        <span
                                            :class="[
                                                'ml-2 truncate text-gray-800 opacity-80',
                                                active ? 'text-white' : 'text-gray-800',
                                            ]"
                                        >
                                            {{ person.email }}
                                        </span>
                                    </div>
                                    <span
                                        v-if="selected"
                                        :class="[
                                            'absolute inset-y-0 right-0 flex items-center pr-4',
                                            active ? 'text-white' : 'text-gray-500',
                                        ]"
                                    >
                                        <CheckIcon class="h-5 w-5" aria-hidden="true" />
                                    </span>
                                </li>
                            </ComboboxOption>
                        </ComboboxOptions>
                    </Combobox>
                </div>
            </div>
        </div>
        <div class="flex gap-1 2xl:gap-2">
            <button
                type="button"
                @click="toggleCC"
                :class="[
                    'inline-flex items-center justify-center rounded-full w-10 h-10 2xl:w-11 2xl:h-11 text-sm font-semibold transition-all duration-200',
                    activeType === 'CC' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-400 hover:bg-gray-200',
                ]"
                class="focus:outline-none"
            >
                CC
            </button>
            <button
                type="button"
                @click="toggleBCC"
                :class="[
                    'inline-flex items-center justify-center rounded-full w-10 h-10 2xl:w-11 2xl:h-11 text-sm font-semibold transition-all duration-200',
                    activeType === 'BCC' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-400 hover:bg-gray-200',
                ]"
                class="focus:outline-none"
            >
                CCI
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, type Ref } from "vue";
import { i18n } from "@/global/preferences";
import { Recipient } from "@/global/types";
import { Combobox, ComboboxButton, ComboboxInput, ComboboxOption, ComboboxOptions } from "@headlessui/vue";
import { ChevronUpDownIcon } from "@heroicons/vue/24/outline";

const isFocus = ref(false);
const activeType = ref("");
const selectedPerson = ref("");
const query = ref("");
const isFirstTimeDestinary = ref<boolean>(true);
const contacts = inject<Ref<Recipient[]>>("contacts", ref([]));
const selectedCC = inject<Ref<Recipient[]>>("selectedCC") || ref([]);
const selectedBCC = inject<Ref<Recipient[]>>("selectedBCC") || ref([]);
const selectedPeople = inject<Ref<Recipient[]>>("selectedPeople") || ref([]);
const stepContainer = inject<Ref<number>>("stepContainer") || ref(0);
const askContent = inject<() => void>("askContent");

const displayPopup = inject<(type: "success" | "error", title: string, message: string) => void>("displayPopup");

const getFilteredPeople = (query: typeof query, contacts: Recipient[]) => {
    let filtered: Recipient[] = [];
    if (query.value === "") {
        filtered = contacts;
    } else {
        const searchTerms = query.value
            .toLowerCase()
            .split(/\s+/)
            .filter((term) => term.length > 0);
        filtered = contacts.filter((person: Recipient) => {
            if (!person.username) {
                if (person.email) {
                    person.username = person.email
                        .split("@")[0]
                        .split(/\.|-/)
                        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
                        .join(" ");
                } else {
                    person.username = "";
                }
            }
            const usernameLower = person.username.toLowerCase();
            const emailLower = person.email.toLowerCase();

            // Check if all search terms match either username or email
            return searchTerms.every((term) => usernameLower.includes(term) || emailLower.includes(term));
        });
    }

    const uniqueResults: Recipient[] = [];
    const seenEmails = new Set<string>();

    filtered.forEach((person) => {
        if (!seenEmails.has(person.email)) {
            seenEmails.add(person.email);
            uniqueResults.push(person);
        }
    });

    return uniqueResults;
};

const filteredPeople = computed(() => getFilteredPeople(query, contacts.value));

function toggleCC() {
    activeType.value = activeType.value === "CC" ? "" : "CC";
}

function toggleBCC() {
    activeType.value = activeType.value === "BCC" ? "" : "BCC";
}

function handleFocus() {
    isFocus.value = true;
}

function handleEnterKey(event: KeyboardEvent) {
    if (isFocus.value) {
        event.preventDefault();
        const target = event.target as HTMLInputElement | null;
        if (target && target.value !== undefined) {
            handleBlur({ target: { value: target.value } });
        }
    }
}

function handleBlur(event: { target: { value: string } }) {
    isFocus.value = false;
    query.value = "";
    const subjectInput = event.target.value.trim().toLowerCase();
    const emailFormat = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (subjectInput && emailFormat.test(subjectInput)) {
        if (!contacts.value.find((person) => person.email === subjectInput)) {
            const newPerson = { email: subjectInput, username: "", id: 0 };
            contacts.value.push(newPerson);
            selectedPeople.value.push(newPerson);
        }
    } else if (!filteredPeople.value.length && subjectInput) {
        displayPopup?.(
            "error",
            i18n.global.t("constants.popUpConstants.errorMessages.invalidEmail"),
            i18n.global.t("constants.popUpConstants.errorMessages.emailFormatIncorrect")
        );
    }
}

function personSelected(person: Recipient) {
    if (!person) return;
    query.value = "";
    switch (activeType.value) {
        case "CC":
            if (!selectedCC.value.includes(person)) {
                selectedCC.value.push(person);
            }
            break;
        case "BCC":
            if (!selectedBCC.value.includes(person)) {
                selectedBCC.value.push(person);
            }
            break;
        default:
            if (!selectedPeople.value.includes(person)) {
                selectedPeople.value.push(person);
            }
    }
    if (isFirstTimeDestinary.value) {
        stepContainer.value = 1;
        askContent?.();
        isFirstTimeDestinary.value = false;
    }
    selectedPerson.value = "";
}
</script>
