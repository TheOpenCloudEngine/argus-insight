package org.opencloudengine.argus.catalog.collector.hql.hook;

import org.apache.hadoop.hive.conf.HiveConf;
import org.apache.hadoop.hive.ql.QueryPlan;
import org.apache.hadoop.hive.ql.hooks.ExecuteWithHookContext;
import org.apache.hadoop.hive.ql.hooks.HookContext;
import org.apache.hadoop.security.UserGroupInformation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.apache.hadoop.hive.ql.hooks.ReadEntity;
import org.apache.hadoop.hive.ql.hooks.WriteEntity;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Hive Query를 Hive Server에서 수신하여, Endpoint로 발송하는 Hook.
 *
 * @author KIM BYOUNG GON (fharenheit@gmail.com)
 */
public class QueryAuditHook implements ExecuteWithHookContext {

    private static final Logger LOG = LoggerFactory.getLogger(ExecuteWithHookContext.class);

    private static final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");

    public static final String PROP_TARGET_URL = "QueryAuditHook.target.url";
    public static final String PROP_ENABLED = "QueryAuditHook.enabled";
    public static final String PROP_PLATFORM_ID = "QueryAuditHook.platform.id";

    private HttpRequestHelper helper;

    public QueryAuditHook() {
        HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_2).connectTimeout(Duration.ofSeconds(3)).build();
        this.helper = new HttpRequestHelper(client);
    }

    @Override
    public void run(HookContext context) throws Exception {

        HiveConf conf = context.getConf();
        boolean isEnabled = conf.getBoolean(PROP_ENABLED, false); // 기본값 false
        if (!isEnabled) {
            LOG.debug("ConfigurableHook is disabled via configuration.");
            return;
        }

        String targetUrl = conf.getTrimmed(PROP_TARGET_URL, null); // 기본값 null, getTrimmed()는 앞뒤 공백 제거
        if (targetUrl == null || targetUrl.isEmpty()) {
            LOG.warn("Target URL is not configured. Set '{}' in hive-site.xml.", PROP_TARGET_URL);
            return;
        }

        String platformId = conf.getTrimmed(PROP_PLATFORM_ID, ""); // 카탈로그 플랫폼 식별자

        QueryPlan queryPlan = context.getQueryPlan();
        if (queryPlan == null) {
            LOG.warn("QueryPlan is null for hook type: {}", context.getHookType());
            return;
        }

        String queryId = queryPlan.getQueryId();
        String queryString = queryPlan.getQueryString();
        String shortUsername = getUser(context);
        String username = context.getUserName();
        String operationName = context.getOperationName();
        long eventTimestamp = System.currentTimeMillis();

        // HookContext에서 입출력 테이블 추출
        List<String> inputs = extractTableNames(context.getInputs());
        List<String> outputs = extractTableNames(context.getOutputs());

        HookContext.HookType hookType = context.getHookType();

        switch (hookType) {
            case PRE_EXEC_HOOK: // 쿼리 시작 시점 기록 (QueryPlan에 기록된 시작 시각 사용)
                long queryStartTime = queryPlan.getQueryStartTime();
                String startTimeStr = formatTimestamp(queryStartTime);

                Map<String, Object> pre = new java.util.HashMap<>();
                pre.put("queryId", queryId);
                pre.put("shortUsername", shortUsername);
                pre.put("username", username);
                pre.put("operationName", operationName);
                pre.put("startTime", String.valueOf(queryStartTime));
                pre.put("query", queryString);
                pre.put("status", "RUNNING");
                pre.put("platformId", platformId);
                pre.put("inputs", inputs);
                pre.put("outputs", outputs);

                LOG.debug("Hive Query Audit을 송신할 메시지: {}", pre);

                try {
                    helper.post(targetUrl, pre, Map.class);
                    LOG.info("[PRE] QueryId: {}, Short Username: {}, Username: {}, Operation: {}, StartTime: {}, Query: {}", queryId, shortUsername, username, operationName, startTimeStr, queryString);
                } catch (Exception e) {
                    LOG.warn("Hive Query Audit을 송신할 수 없습니다. 원인: {}", e.getMessage(), e);
                }

                break;

            case POST_EXEC_HOOK: // 쿼리 성공 종료 시점 및 소요 시간 기록
                long postStartTime = queryPlan.getQueryStartTime();
                long postEndTime = eventTimestamp; // Hook 호출 시점이 종료 시점 근사치
                long postDuration = (postStartTime > 0) ? (postEndTime - postStartTime) : -1;
                String postEndTimeStr = formatTimestamp(postEndTime);

                Map<String, Object> successWithStatus = new java.util.HashMap<>();
                successWithStatus.put("queryId", queryId);
                successWithStatus.put("shortUsername", shortUsername);
                successWithStatus.put("username", username);
                successWithStatus.put("operationName", operationName);
                successWithStatus.put("startTime", String.valueOf(postStartTime));
                successWithStatus.put("endTime", String.valueOf(postEndTime));
                successWithStatus.put("durationMs", String.valueOf(postDuration));
                successWithStatus.put("query", queryString);
                successWithStatus.put("status", "SUCCESS");
                successWithStatus.put("platformId", platformId);
                successWithStatus.put("inputs", inputs);
                successWithStatus.put("outputs", outputs);

                LOG.debug("Hive Query Audit을 송신할 메시지: {}", successWithStatus);

                try {
                    helper.post(targetUrl, successWithStatus, Map.class);
                    LOG.info("[SUCCESS] QueryId: {}, Short Username: {}, Username: {}, EndTime: {}, DurationMs: {}, Query: {}", queryId, shortUsername, username, postEndTimeStr, postDuration, queryString);
                } catch (Exception e) {
                    LOG.warn("Hive Query Audit을 송신할 수 없습니다. 원인: {}", e.getMessage(), e);
                }

                break;

            case ON_FAILURE_HOOK: // 쿼리 실패 시점 및 소요 시간, 에러 메시지 기록
                long failStartTime = queryPlan.getQueryStartTime();
                long failEndTime = eventTimestamp; // Hook 호출 시점이 실패 시점 근사치
                long failDuration = (failStartTime > 0) ? (failEndTime - failStartTime) : -1;
                String failEndTimeStr = formatTimestamp(failEndTime);
                String errorMsg = "N/A";
                if (context.getException() != null) {
                    errorMsg = context.getException().getMessage();
                }

                Map<String, Object> failedWithStatus = new java.util.HashMap<>();
                failedWithStatus.put("queryId", queryId);
                failedWithStatus.put("shortUsername", shortUsername);
                failedWithStatus.put("username", username);
                failedWithStatus.put("operationName", operationName);
                failedWithStatus.put("startTime", String.valueOf(failStartTime));
                failedWithStatus.put("endTime", String.valueOf(failEndTime));
                failedWithStatus.put("durationMs", String.valueOf(failDuration));
                failedWithStatus.put("errorMsg", errorMsg);
                failedWithStatus.put("query", queryString);
                failedWithStatus.put("status", "FAILED");
                failedWithStatus.put("platformId", platformId);
                failedWithStatus.put("inputs", inputs);
                failedWithStatus.put("outputs", outputs);

                LOG.debug("Hive Query Audit을 송신할 메시지: {}", failedWithStatus);

                try {
                    helper.post(targetUrl, failedWithStatus, Map.class);
                    LOG.warn("[FAILURE] QueryId: {}, Short Username: {}, Username: {}, EndTime: {}, DurationMs: {}, Error: {}, Query: {}", queryId, shortUsername, username, failEndTimeStr, failDuration, errorMsg, queryString);
                } catch(Exception e) {
                    LOG.warn("Hive Query Audit을 송신할 수 없습니다. 원인: {}", e.getMessage(), e);
                }

                break;

            default:
                // 다른 타입의 Hook (사용하지 않는 경우)
                break;
        }
    }

    private String getUser(HookContext hookContext) {
        UserGroupInformation ugi = hookContext.getUgi();
        return (ugi == null) ? "unknown" : ugi.getShortUserName();
    }

    private String formatTimestamp(long timestampMillis) {
        if (timestampMillis <= 0) return "N/A";
        return LocalDateTime.ofInstant(Instant.ofEpochMilli(timestampMillis), ZoneId.systemDefault()).format(formatter);
    }

    /**
     * ReadEntity/WriteEntity Set에서 TABLE 타입인 항목의 "db.table" 이름을 추출한다.
     */
    @SuppressWarnings("rawtypes")
    private List<String> extractTableNames(Set entities) {
        List<String> names = new ArrayList<>();
        if (entities == null) {
            return names;
        }
        for (Object entity : entities) {
            try {
                if (entity instanceof ReadEntity) {
                    ReadEntity re = (ReadEntity) entity;
                    if (re.getType() == ReadEntity.Type.TABLE && re.getTable() != null) {
                        names.add(re.getTable().getDbName() + "." + re.getTable().getTableName());
                    }
                } else if (entity instanceof WriteEntity) {
                    WriteEntity we = (WriteEntity) entity;
                    if (we.getType() == WriteEntity.Type.TABLE && we.getTable() != null) {
                        names.add(we.getTable().getDbName() + "." + we.getTable().getTableName());
                    }
                }
            } catch (Exception e) {
                LOG.debug("Failed to extract table name from entity: {}", entity, e);
            }
        }
        return names;
    }
}
