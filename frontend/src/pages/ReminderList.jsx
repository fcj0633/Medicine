import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { familyAPI, reminderAPI } from '../api';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  Edit3,
  Loader2,
  Trash2,
  Volume2,
  X,
} from 'lucide-react';

const MEAL_TEXT_MAP = {
  before_meal: '饭前',
  after_meal: '饭后',
  empty_stomach: '空腹',
  before_sleep: '睡前',
};

const REPEAT_TEXT_MAP = {
  everyday: '每天',
  'mon,wed,fri': '周一三五',
  'tue,thu,sat': '周二四六',
};

const STATUS_META = {
  pending: {
    label: '待服药',
    Icon: Bell,
    textClass: 'text-orange-500',
    badgeClass: 'bg-orange-100 text-orange-700',
    cardClass: 'animate-pulse-remind border-orange-300',
  },
  taken: {
    label: '已服药',
    Icon: CheckCircle,
    textClass: 'text-green-600',
    badgeClass: 'bg-green-100 text-green-700',
    cardClass: 'border-green-200 bg-green-50/60',
  },
  late: {
    label: '迟服',
    Icon: Clock,
    textClass: 'text-yellow-600',
    badgeClass: 'bg-yellow-100 text-yellow-700',
    cardClass: 'border-yellow-200 bg-yellow-50/60',
  },
  missed: {
    label: '漏服',
    Icon: AlertTriangle,
    textClass: 'text-red-600',
    badgeClass: 'bg-red-100 text-red-700',
    cardClass: 'border-red-200 bg-red-50/60',
  },
};

const getMealText = (mealRelation) => MEAL_TEXT_MAP[mealRelation] || '';

const getRepeatText = (repeatDays) => REPEAT_TEXT_MAP[repeatDays] || repeatDays || '每天';

const getStatusMeta = (status) => STATUS_META[status] || STATUS_META.pending;

const getActualTimeText = (actualTime) => {
  if (typeof actualTime !== 'string' || actualTime.length < 16) {
    return '';
  }
  return actualTime.slice(11, 16);
};

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

  const mergeTodayStatus = (reminderList, todayStatus) => {
    const statusMap = new Map(
      (todayStatus?.items || []).map((item) => [item.reminder_id, item])
    );

    return reminderList.map((reminder) => {
      const statusItem = statusMap.get(reminder.id);
      return {
        ...reminder,
        status: statusItem?.status || 'pending',
        actual_time: statusItem?.actual_time || null,
      };
    });
  };

  const loadReminders = async (userId) => {
    setLoading(true);
    try {
      const remindersRes = await reminderAPI.getAll(userId);

      if (!isElderly) {
        setReminders(remindersRes.data);
        return;
      }

      try {
        const todayStatusRes = await reminderAPI.getTodayStatus(userId);
        setReminders(mergeTodayStatus(remindersRes.data, todayStatusRes.data));
      } catch (statusError) {
        console.error('加载今日服药状态失败:', statusError);
        setReminders(mergeTodayStatus(remindersRes.data, { items: [] }));
      }
    } catch (error) {
      console.error('加载提醒失败:', error);
      setReminders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!user) {
      return;
    }

    if (user.role === 'family') {
      setLoading(true);
      familyAPI
        .getMyElderly()
        .then((res) => {
          const list = res.data || [];
          setElderlyList(list);
          if (list.length > 0) {
            setSelectedUserId((prev) => prev ?? list[0].id);
          } else {
            setReminders([]);
            setLoading(false);
          }
        })
        .catch((error) => {
          console.error('加载老人列表失败:', error);
          setElderlyList([]);
          setReminders([]);
          setLoading(false);
        });
      return;
    }

    loadReminders();
  }, [user, isElderly]);

  useEffect(() => {
    if (user?.role === 'family' && selectedUserId) {
      loadReminders(selectedUserId);
    }
  }, [selectedUserId, user?.role]);

  const handleConfirm = async (reminderId) => {
    try {
      await reminderAPI.confirmMedication(reminderId);
      setShowConfirmModal(null);
      await loadReminders(selectedUserId);
    } catch (error) {
      alert(`确认失败：${error.response?.data?.detail || '未知错误'}`);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('确定要删除这个提醒吗？')) {
      return;
    }

    try {
      await reminderAPI.delete(id);
      await loadReminders(selectedUserId);
    } catch (error) {
      console.error('删除提醒失败:', error);
      alert('删除失败，请稍后重试');
    }
  };

  const handleUpdate = async (id) => {
    try {
      await reminderAPI.update(id, editForm);
      setEditingId(null);
      await loadReminders(selectedUserId);
    } catch (error) {
      console.error('更新提醒失败:', error);
      alert('更新失败，请稍后重试');
    }
  };

  const speakWithBrowser = (text) => {
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'zh-CN';
      utterance.rate = 0.8;
      speechSynthesis.speak(utterance);
    }
  };

  const playAudio = async (id) => {
    try {
      const res = await reminderAPI.getAudio(id);
      if (res.data.url && audioRef.current) {
        audioRef.current.src = res.data.url;
        audioRef.current.onerror = () => {
          if (res.data.text) {
            speakWithBrowser(res.data.text);
          }
        };
        audioRef.current.play().catch(() => {
          if (res.data.text) {
            speakWithBrowser(res.data.text);
          }
        });
      } else if (res.data.text) {
        speakWithBrowser(res.data.text);
      }
    } catch (error) {
      console.error('播放提醒音频失败:', error);
      const reminder = reminders.find((item) => item.id === id);
      if (reminder && 'speechSynthesis' in window) {
        const text = `吃药提醒：请在${reminder.reminder_time}服用${reminder.drug?.name || '药品'}，${reminder.dosage || '按说明书服用'}。`;
        speakWithBrowser(text);
      }
    }
  };

  const renderStatusBadge = (status) => {
    const meta = getStatusMeta(status);
    const Icon = meta.Icon;

    return (
      <span className={`flex items-center gap-1 font-bold ${meta.textClass}`}>
        <Icon className={isElderly ? 'w-6 h-6 sm:w-7 sm:h-7' : 'w-5 h-5'} />
        {meta.label}
      </span>
    );
  };

  const emptyMessage =
    user?.role === 'family' && elderlyList.length === 0
      ? '请先绑定老人账号后再管理提醒。'
      : isElderly
        ? '还没有吃药提醒，可以先去拍照识药添加药品。'
        : '还没有提醒，先去添加药品再生成提醒吧。';

  return (
    <div className="space-y-4 sm:space-y-6">
      <audio ref={audioRef} className="hidden" />

      <h1 className={`${isElderly ? 'text-2xl sm:text-elder-2xl' : 'text-xl sm:text-2xl'} font-bold text-gray-800`}>
        {isElderly ? '吃药提醒' : '提醒管理'}
      </h1>

      {user?.role === 'family' && elderlyList.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {elderlyList.map((elderly) => (
            <button
              key={elderly.id}
              onClick={() => setSelectedUserId(elderly.id)}
              className={`px-4 py-2 rounded-xl font-medium whitespace-nowrap active:scale-95 transition ${
                selectedUserId === elderly.id
                  ? 'bg-blue-500 text-white'
                  : 'bg-white text-gray-600 border'
              }`}
            >
              {elderly.display_name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-10 h-10 animate-spin text-orange-500" />
        </div>
      ) : reminders.length === 0 ? (
        <div className="card-elder text-center py-10">
          <Bell className="w-14 h-14 sm:w-16 sm:h-16 text-gray-300 mx-auto mb-4" />
          <p className={`${isElderly ? 'text-base sm:text-elder-base' : 'text-base sm:text-lg'} text-gray-500`}>
            {emptyMessage}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reminders.map((reminder) => {
            const status = isElderly ? reminder.status || 'pending' : reminder.status;
            const statusMeta = getStatusMeta(status);
            const actualTimeText = getActualTimeText(reminder.actual_time);

            return (
              <div
                key={reminder.id}
                className={`card-elder transition ${isElderly ? statusMeta.cardClass : ''}`}
              >
                {editingId === reminder.id ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-600 mb-1">提醒时间</label>
                        <input
                          type="time"
                          value={editForm.reminder_time || ''}
                          onChange={(e) => setEditForm({ ...editForm, reminder_time: e.target.value })}
                          className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-600 mb-1">剂量</label>
                        <input
                          type="text"
                          value={editForm.dosage || ''}
                          onChange={(e) => setEditForm({ ...editForm, dosage: e.target.value })}
                          className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-600 mb-1">服用时机</label>
                        <select
                          value={editForm.meal_relation || ''}
                          onChange={(e) => setEditForm({ ...editForm, meal_relation: e.target.value })}
                          className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none"
                        >
                          <option value="">不限</option>
                          <option value="before_meal">饭前</option>
                          <option value="after_meal">饭后</option>
                          <option value="empty_stomach">空腹</option>
                          <option value="before_sleep">睡前</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-600 mb-1">重复</label>
                        <select
                          value={editForm.repeat_days || 'everyday'}
                          onChange={(e) => setEditForm({ ...editForm, repeat_days: e.target.value })}
                          className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:border-orange-400 focus:outline-none"
                        >
                          <option value="everyday">每天</option>
                          <option value="mon,wed,fri">周一三五</option>
                          <option value="tue,thu,sat">周二四六</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleUpdate(reminder.id)}
                        className="flex-1 py-3 bg-green-600 text-white font-bold rounded-xl active:scale-95"
                      >
                        保存
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="flex-1 py-3 bg-gray-200 text-gray-600 font-bold rounded-xl active:scale-95"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
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
                      <button
                        onClick={() => playAudio(reminder.id)}
                        className="ml-auto p-2 bg-blue-100 text-blue-600 rounded-xl active:scale-95"
                        title="语音播报"
                      >
                        <Volume2 className={isElderly ? 'w-6 h-6' : 'w-5 h-5'} />
                      </button>
                    </div>

                    <div className="mb-2">
                      <div className={`${isElderly ? 'text-lg sm:text-elder-lg' : 'text-base sm:text-lg'} font-bold text-gray-800`}>
                        {reminder.drug?.name || '未知药品'}
                      </div>
                      <div className={`${isElderly ? 'text-base' : 'text-sm'} text-gray-500`}>
                        {reminder.dosage || '按说明书服用'}
                      </div>
                    </div>

                    {isElderly ? (
                      <div className="flex items-center justify-between gap-3">
                        <div className="space-y-1">
                          {renderStatusBadge(status)}
                          {status !== 'pending' && actualTimeText && (
                            <div className="text-sm text-gray-500">确认时间：{actualTimeText}</div>
                          )}
                        </div>

                        {status === 'pending' && (
                          <div className="flex flex-col items-end gap-2">
                            <span className="text-sm text-orange-700 font-medium">吃完后再点确认</span>
                            <button
                              onClick={() => setShowConfirmModal(reminder)}
                              className="btn-elder-warning"
                            >
                              确认服药
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => {
                            setEditingId(reminder.id);
                            setEditForm({
                              reminder_time: reminder.reminder_time,
                              dosage: reminder.dosage || '',
                              meal_relation: reminder.meal_relation || '',
                              repeat_days: reminder.repeat_days || 'everyday',
                            });
                          }}
                          className="p-2.5 bg-gray-100 text-gray-600 rounded-xl active:scale-95"
                          title="编辑"
                        >
                          <Edit3 className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleDelete(reminder.id)}
                          className="p-2.5 bg-red-100 text-red-600 rounded-xl active:scale-95"
                          title="删除"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50">
          <div
            className="bg-white rounded-t-3xl sm:rounded-3xl p-6 sm:p-8 w-full sm:max-w-md space-y-5"
            style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 16px), 24px)' }}
          >
            <div className="flex justify-between items-start">
              <h2 className="text-xl sm:text-elder-xl font-bold text-gray-800">确认服药</h2>
              <button
                onClick={() => setShowConfirmModal(null)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="w-7 h-7" />
              </button>
            </div>

            <div className="text-center space-y-2">
              <div className="text-xl sm:text-elder-xl font-bold text-orange-600">
                {showConfirmModal.drug?.name || '未知药品'}
              </div>
              <div className="text-lg sm:text-elder-lg text-gray-600">{showConfirmModal.reminder_time}</div>
              <div className="text-base sm:text-elder-base text-gray-500">
                {showConfirmModal.dosage || '按说明书服用'}
              </div>
              {getMealText(showConfirmModal.meal_relation) && (
                <div className="text-sm sm:text-base text-orange-700 font-medium">
                  {getMealText(showConfirmModal.meal_relation)}服用
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setShowConfirmModal(null)}
                className="py-4 bg-gray-200 text-gray-700 font-bold rounded-2xl text-lg active:scale-95"
              >
                还没吃
              </button>
              <button
                onClick={() => handleConfirm(showConfirmModal.id)}
                className="py-4 bg-green-600 text-white font-bold rounded-2xl text-lg active:scale-95 shadow-lg hover:bg-green-700"
              >
                确认已服药
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
