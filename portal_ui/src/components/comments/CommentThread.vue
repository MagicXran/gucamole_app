<template>
  <section class="comment-thread">
    <header class="comment-thread__header">
      <h2>评论</h2>
      <p>只保留最小闭环：看得到，也发得出。</p>
    </header>

    <div v-if="loading" class="comment-thread__state">评论加载中...</div>
    <div v-else-if="errorMessage" class="comment-thread__state comment-thread__state--error">{{ errorMessage }}</div>
    <div v-else-if="items.length === 0" class="comment-thread__state">还没有评论</div>

    <ul v-else class="comment-thread__list">
      <li v-for="item in items" :key="`${item.target_type}-${item.target_id}-${item.id}-${item.created_at || ''}`">
        <div class="comment-thread__meta">
          <strong>{{ item.author_name }}</strong>
          <span>{{ item.created_at || '刚刚' }}</span>
        </div>
        <p>{{ item.content }}</p>
      </li>
    </ul>

    <form data-testid="comment-submit" class="comment-thread__composer" @submit.prevent="submitComment">
      <textarea
        data-testid="comment-input"
        v-model="draft"
        rows="3"
        :disabled="submitting"
        placeholder="写点有用的，别灌水。"
      />
      <button type="submit" :disabled="submitting">{{ submitting ? '提交中...' : '发表评论' }}</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { createComment, listComments } from '@/services/api/comments'
import type { CommentItem, CommentTargetType } from '@/types/comments'

const props = defineProps<{
  targetType: CommentTargetType
  targetId: number
}>()

const items = ref<CommentItem[]>([])
const loading = ref(false)
const submitting = ref(false)
const draft = ref('')
const errorMessage = ref('')
const requestToken = ref(0)

async function loadComments() {
  if (!props.targetId) {
    items.value = []
    loading.value = false
    return
  }
  const currentToken = requestToken.value + 1
  requestToken.value = currentToken
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listComments(props.targetType, props.targetId)
    if (currentToken !== requestToken.value) {
      return
    }
    items.value = response.data
  } catch (error) {
    if (currentToken !== requestToken.value) {
      return
    }
    items.value = []
    errorMessage.value = error instanceof Error ? error.message : '评论加载失败'
  } finally {
    if (currentToken !== requestToken.value) {
      return
    }
    loading.value = false
  }
}

async function submitComment() {
  const content = draft.value.trim()
  if (!content || submitting.value) {
    return
  }
  submitting.value = true
  errorMessage.value = ''
  try {
    const response = await createComment({
      target_type: props.targetType,
      target_id: props.targetId,
      content,
    })
    items.value = [...items.value, response.data]
    draft.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '评论提交失败'
  } finally {
    submitting.value = false
  }
}

watch(() => `${props.targetType}:${props.targetId}`, () => {
  draft.value = ''
  void loadComments()
})

onMounted(() => {
  void loadComments()
})
</script>

<style scoped>
.comment-thread {
  display: grid;
  gap: 14px;
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
}

.comment-thread__header,
.comment-thread__composer,
.comment-thread__list,
.comment-thread__list li {
  display: grid;
  gap: 8px;
}

.comment-thread__header h2,
.comment-thread__header p,
.comment-thread__list p {
  margin: 0;
}

.comment-thread__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 13px;
}

.comment-thread__state {
  color: #475569;
}

.comment-thread__state--error {
  color: #b91c1c;
}

.comment-thread__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.comment-thread__list li {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
}

.comment-thread__composer textarea {
  width: 100%;
  min-height: 96px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 10px 12px;
  resize: vertical;
  font: inherit;
}

.comment-thread__composer button {
  width: fit-content;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
