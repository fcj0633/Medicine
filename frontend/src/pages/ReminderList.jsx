import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { reminderAPI, familyAPI } from '../api';
import { Bell, Plus, Trash2, Edit3, Volume2, Clock, Loader2, X } from 'lucide-react';

export default function ReminderList() {
  const { user } = useAuth();
  const isElderly = user?.role === 'elderly';
  const audioRef = useRef(null);

  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [elderlyList, setElderlyList] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [showConfirmModal, setShowConfirmModal] = useState(null);

  useEffect(() => {
    if (user?.role === 'family') {
      familyAPI.getMyElderly().then(res => {
        setElderlyList(res.data);
        if (res.data.length > 0) setSelectedUserId(res.data[0].id);
      }).catch(() => {});
    } else {
      loadReminders();
    }
  }, []);

  useEffect(() => {
    if (selectedUserId) loadReminders(selectedUserId);
  }, [selectedUserId]);

  const loadReminders = async (userId) => {
    setLoading(true);
    try {
      const res = await reminderAPI.getAll(userId);
      setReminders(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (reminderId) => {
    try {
      await reminderAPI.confirmMedication(reminderId);
      setShowConfirmModal(null);
      loadReminders(selectedUserId);
      alert('✅ 服药确认成功！');
    } catch (err) {
      alert('确认失败：' + (err.response?.data?.detail || '未知错误'));
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('确定要删除这个提醒吗？')) return;
    try {
      await reminderAPI.delete(id);
      loadReminders(selectedUserId);
    } catch (err) {
      alert('删除失败');
    }
  };

  const handleUpdate = async (id) => {
    try {
      await reminderAPI.update(id, editForm);
      setEditingId(null);
      loadReminders(selectedUserId);
    } catch (err) {
      alert('更新失败');
    }
  };

  const speakWithBrowser = (text) => {
    if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-CN';
      u.rate = 0.8;
      speechSynthesis.speak(u);
    }
  };

  const playAudio = async (id) => {
    try {
      const res = await reminderAPI.getAudio(id);
      if (res.data.url && audioRef.current) {
        audioRef.current.src = res.data.url;
        audioRef.current.onerror = () => {
          if (res.data.text) speakWithBrowser(res.data.text);
        };
        audioRef.current.play().catch(() => {
          if (res.data.text) speakWithBrowser(res.data.text);
        });
      } else if (res.data.text) {
        speakWithBrowser(res.data.text);
      }
    } catch {
      // 回退到浏览器TTS
      const reminder = reminders.find(r => r.id === id);
      if (reminder && 'speechSynthesis' in window) {
        const text = `吃药提醒：请在${reminder.reminder_time}服用${reminder.drug?.name || '药品'}，${reminder.dosage || '按说明书服用'}`;
        speakWithBrowser(text);
      }
    }
  };

  const getMealText = (meal) => {
    const map = { before_meal: '饭前', after_meal: '饭后', empty_stomach: '空腹', before_sleep: '睡前' };
    return map[meal] || '';
  };

  const getRepeatText = (days) => {
    if (days === 'everyday') return '每天';
    return days;
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <audio ref={audioRef} className="hidden" />

      <h1 className={`${isElderly ? 'text-2xl sm:text-elder-2xl' : 'text-xl sm:text-2xl'} font-bold text-gray-800`}>
        {isElderly ? '吃药提醒' : '提醒管理'}
      </h1>

      {/* 家属选人 */}
      {user?.role === 'family' && elderlyList.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {elderlyList.map(e => (
            <button key={e.id} onClick={() => setSelectedUserId(e.id)}
              className={`px-4 py-2 rounded-xl font-medium whitespace-nowrap active:scale-95 transition ${
                selectedUserId === e.id ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 border'
              }`}>
              {e.display_name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-10 h-10 animate-spin text-orange-500" /></div>
      ) : reminders.length === 0 ? (
        <div className="card-elder text-center py-10">
          <Bell className="w-14 h-14 sm:w-16 sm:h-16 text-gray-300 mx-auto mb-4" />
          <p className={`${isElderly ? 'text-base sm:text-elder-base' : 'text-base sm:text-lg'} text-gray-500`}>
            还没有提醒，先去添加药品再生成提醒吧
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reminders.map((reminder) => (
            <div key={reminder.id} className="card-elder transition">
              {editingId === reminder.id ? (
                /* 编辑模式 */
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-600 mb-1">提醒时间</label>
                      <input type="time" value={editForm.reminder_time || ''}
                        onChange={(e) => setEditForm({ ...editForm, reminder_time: e.target.value })}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-600 mb-1">剂量</label>
                      <input type="text" value={editForm.dosage || ''}
                        onChange={(e) => setEditForm({ ...editForm, dosage: e.target.value })}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-600 mb-1">饭前/饭后</label>
                      <select value={editForm.meal_relation || ''}
                        onChange={(e) => setEditForm({ ...editForm, meal_relation: e.target.value })}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none">
                        <option value="">不限</option>
                        <option value="before_meal">饭前</option>
                        <option value="after_meal">饭后</option>
                        <option value="empty_stomach">空腹</option>
                        <option value="before_sleep">睡前</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-600 mb-1">重复</label>
                      <select value={editForm.repeat_days || 'everyday'}
                        onChange={(e) => setEditForm({ ...editForm, repeat_days: e.target.value })}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none">
                        <option value="everyday">每天</option>
                        <option value="mon,wed,fri">周一三五</option>
                        <option value="tue,thu,sat">周二四六</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => handleUpdate(reminder.id)}
                      className="flex-1 py-3 bg-green-600 text-white font-bold rounded-xl active:scale-95">保存</button>
                    <button onClick={() => setEditingId(null)}
                      className="flex-1 py-3 bg-gray-200 text-gray-600 font-bold rounded-xl active:scale-95">取消</button>
                  </div>
                </div>
              ) : (
                /* 展示模式 - 移动端竖向堆叠 */
                <div>
                  {/* 第一行：时间 + 标签 + 语音 */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`${isElderly ? 'text-xl sm:text-elder-2xl' : 'text-xl sm:text-2xl'} font-bold text-orange-600`}>
                      {reminder.reminder_time}
                    </span>
                    {getMealText(reminder.meal_relation) && (
                      <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full">
                        {getMealText(reminder.meal_relation)}
                      </span>
                    )}
                    <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                      {getRepeatText(reminder.repeat_days)}
                    </span>
                    <button onClick={() => playAudio(reminder.id)}
                      className="ml-auto p-2 bg-blue-100 text-blue-600 rounded-xl active:scale-95" title="语音播报">
                      <Volume2 className={isElderly ? 'w-6 h-6' : 'w-5 h-5'} />
                    </button>
                  </div>

                  {/* 第二行：药品信息 */}
                  <div className="mb-2">
                    <div className={`${isElderly ? 'text-lg sm:text-elder-lg' : 'text-base sm:text-lg'} font-bold text-gray-800`}>
                      {reminder.drug?.name || '未知药品'}
                    </div>
                    <div className={`${isElderly ? 'text-base' : 'text-sm'} text-gray-500`}>
                      {reminder.dosage || '按说明书服用'}
                    </div>
                  </div>

                  {/* 第三行：操作按钮 */}
                  <div className="flex gap-2 justify-end">
                    {isElderly && (
                      <div className="flex flex-col items-end gap-2">
                        <span className="text-sm text-orange-700 font-medium">吃完后再点确认</span>
                        <button
                          onClick={() => setShowConfirmModal(reminder)}
                          className="px-5 py-2.5 bg-orange-500 text-white font-bold rounded-xl text-base active:scale-95 shadow hover:bg-orange-600"
                        >
                          去确认服药
                        </button>
                      </div>
                    )}
                    {!isElderly && (
                      <>
                        <button onClick={() => { setEditingId(reminder.id); setEditForm(reminder); }}
                          className="p-2.5 bg-gray-100 text-gray-600 rounded-xl active:scale-95" title="编辑">
                          <Edit3 className="w-5 h-5" />
                        </button>
                        <button onClick={() => handleDelete(reminder.id)}
                          className="p-2.5 bg-red-100 text-red-600 rounded-xl active:scale-95" title="删除">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 服药确认弹窗（老人端）- 全屏底部弹出 */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50">
          <div className="bg-white rounded-t-3xl sm:rounded-3xl p-6 sm:p-8 w-full sm:max-w-md space-y-5"
               style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 16px), 24px)' }}>
            <div className="flex justify-between items-start">
              <h2 className="text-xl sm:text-elder-xl font-bold text-gray-800">确认服药</h2>
              <button onClick={() => setShowConfirmModal(null)} className="p-1 text-gray-400 hover:text-gray-600">
                <X className="w-7 h-7" />
              </button>
            </div>
            <div className="text-center space-y-2">
              <div className="text-xl sm:text-elder-xl font-bold text-orange-600">{showConfirmModal.drug?.name}</div>
              <div className="text-lg sm:text-elder-lg text-gray-600">{showConfirmModal.reminder_time}</div>
              <div className="text-base sm:text-elder-base text-gray-500">{showConfirmModal.dosage}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => setShowConfirmModal(null)}
                className="py-4 bg-gray-200 text-gray-700 font-bold rounded-2xl text-lg active:scale-95">
                还没吃
              </button>
              <button onClick={() => handleConfirm(showConfirmModal.id)}
                className="py-4 bg-green-600 text-white font-bold rounded-2xl text-lg active:scale-95 shadow-lg">
                确认已服药
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
